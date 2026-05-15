from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from apps.permissions.constants import VIEW_PURCHASES
from apps.permissions.decorators import PermissionRequiredMixin

from .forms import PurchaseForm, PurchaseItemFormSet, PurchasePaymentForm
from .models import (
    Purchase,
    PurchasePayment,
    _items_total,
    _payments_total_in_purchase_currency,
)


@method_decorator(login_required, name="dispatch")
class PurchaseListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_PURCHASES
    model = Purchase
    template_name = "procurement/list.html"
    paginate_by = 50
    context_object_name = "purchases"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("supplier", "company", "project", "rubro", "original_currency")
        )
        f = self.request.GET

        if f.get("tipo") in {"obra", "admin", "cadeteria"}:
            qs = qs.filter(purchase_type=f["tipo"])
        if f.get("estado"):
            qs = qs.filter(status=f["estado"])
        if f.get("proveedor"):
            qs = qs.filter(supplier_id=f["proveedor"])
        if f.get("obra"):
            qs = qs.filter(project_id=f["obra"])
        if f.get("sociedad"):
            qs = qs.filter(company_id=f["sociedad"])
        if f.get("desde"):
            qs = qs.filter(invoice_date__gte=f["desde"])
        if f.get("hasta"):
            qs = qs.filter(invoice_date__lte=f["hasta"])
        if f.get("q"):
            q = f["q"]
            qs = qs.filter(
                Q(document_number__icontains=q)
                | Q(supplier__name__icontains=q)
                | Q(detail__icontains=q)
                | Q(notes__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        from apps.catalog.models import Supplier
        from apps.companies.models import Company
        from apps.projects.models import Project

        ctx = super().get_context_data(**kwargs)
        f = self.request.GET
        ctx["current_type"] = f.get("tipo", "")
        ctx["current_status"] = f.get("estado", "")
        ctx["current_supplier"] = f.get("proveedor", "")
        ctx["current_project"] = f.get("obra", "")
        ctx["current_company"] = f.get("sociedad", "")
        ctx["current_desde"] = f.get("desde", "")
        ctx["current_hasta"] = f.get("hasta", "")
        ctx["current_q"] = f.get("q", "")
        ctx["status_choices"] = Purchase.Status.choices

        # Choices para los selects
        ctx["suppliers"] = Supplier.objects.filter(active=True).order_by("name")
        ctx["projects"] = Project.objects.filter(is_archived=False).order_by("name")
        ctx["companies"] = Company.objects.filter(active=True).order_by("name")

        # KPIs sobre el queryset filtrado (sin paginación).
        full = self.get_queryset()
        ctx["kpi_total"] = full.count()
        ctx["kpi_to_pay"] = full.filter(status__in=[Purchase.Status.TO_PAY, Purchase.Status.PAID_PARTIAL]).count()
        ctx["kpi_paid"] = full.filter(status=Purchase.Status.PAID).count()
        ctx["kpi_total_amount"] = full.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        return ctx


@method_decorator(login_required, name="dispatch")
class PurchaseDetailView(DetailView):
    model = Purchase
    template_name = "procurement/detail.html"
    context_object_name = "purchase"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related(
                "supplier", "company", "project", "rubro", "subrubro",
                "business_component", "original_currency",
            )
            .prefetch_related("items__material", "items__subcontract", "items__unit")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        purchase: Purchase = self.object  # type: ignore[assignment]
        items_total = _items_total(purchase)
        ctx["items_total"] = items_total
        ctx["items_mismatch"] = (
            purchase.is_itemized
            and items_total
            and abs(items_total - purchase.amount_without_tax) > 0.01
        )
        # Pagos
        payments = list(purchase.payments.select_related("currency").all())
        ctx["payments"] = payments
        ctx["payments_total"] = _payments_total_in_purchase_currency(purchase)
        ctx["payment_form"] = PurchasePaymentForm(purchase=purchase)
        ctx["balance"] = (purchase.total_amount or Decimal("0")) - ctx["payments_total"]
        return ctx


@login_required
def purchase_create(request):
    return _purchase_form(request, instance=None)


@login_required
def purchase_edit(request, pk: int):
    purchase = get_object_or_404(Purchase, pk=pk)
    return _purchase_form(request, instance=purchase)


@login_required
def payment_create(request, pk: int):
    """Registra un pago contra una compra desde el detail."""
    purchase = get_object_or_404(Purchase, pk=pk)
    form = PurchasePaymentForm(request.POST or None, purchase=purchase)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        payment.purchase = purchase
        payment.created_by = request.user
        payment.save()
        messages.success(
            request,
            f"Pago de {payment.amount} {payment.currency.code} registrado.",
        )
        return redirect("procurement:detail", pk=purchase.pk)
    if request.method == "POST":
        messages.error(request, "No se pudo guardar el pago. Revisá los campos.")
    return redirect("procurement:detail", pk=purchase.pk)


@login_required
def payment_delete(request, pk: int, payment_pk: int):
    """Borra un pago. POST-only para que no se dispare por linkeo accidental."""
    if request.method != "POST":
        return redirect("procurement:detail", pk=pk)
    payment = get_object_or_404(PurchasePayment, pk=payment_pk, purchase_id=pk)
    payment.delete()
    messages.success(request, "Pago eliminado.")
    return redirect("procurement:detail", pk=pk)


# ---------------------------------------------------------------------------
# Bandeja "A pagar"
# ---------------------------------------------------------------------------

@login_required
def to_pay_tray(request):
    """Bandeja de tesorería: compras pendientes agrupadas por semana de pago.

    Una compra entra acá cuando:
      - status ∈ {to_pay, paid_partial}
      - y tiene total_amount > 0
    Se agrupan por `week_to_pay` (string libre). Las que no tienen semana
    cargada caen en el grupo "Sin asignar".
    """
    qs = (
        Purchase.objects.filter(
            status__in=[Purchase.Status.TO_PAY, Purchase.Status.PAID_PARTIAL],
            total_amount__gt=0,
        )
        .select_related("supplier", "company", "project", "rubro", "original_currency")
        .order_by("week_to_pay", "due_date", "invoice_date")
    )

    groups: dict[str, dict] = {}
    grand_total = Decimal("0")
    grand_balance = Decimal("0")
    for p in qs:
        paid = _payments_total_in_purchase_currency(p)
        balance = (p.total_amount or Decimal("0")) - paid
        if balance <= 0:
            continue
        key = p.week_to_pay or "Sin asignar"
        if key not in groups:
            groups[key] = {"label": key, "items": [], "total": Decimal("0"), "balance": Decimal("0")}
        groups[key]["items"].append({"purchase": p, "paid": paid, "balance": balance})
        groups[key]["total"] += p.total_amount or Decimal("0")
        groups[key]["balance"] += balance
        grand_total += p.total_amount or Decimal("0")
        grand_balance += balance

    return render(request, "procurement/to_pay.html", {
        "groups": list(groups.values()),
        "grand_total": grand_total,
        "grand_balance": grand_balance,
    })


# ---------------------------------------------------------------------------
# Cuenta corriente por proveedor
# ---------------------------------------------------------------------------

@login_required
def supplier_balance(request):
    """Saldo pendiente por proveedor.

    Para cada proveedor con compras no canceladas, calcula:
      total facturado - total pagado = saldo.
    Solo lista los que tienen saldo > 0 por defecto; con ?todos=1 muestra todos.
    """
    from apps.catalog.models import Supplier

    show_all = request.GET.get("todos") == "1"

    rows = []
    total_balance = Decimal("0")
    suppliers = Supplier.objects.filter(active=True).order_by("name")
    for supplier in suppliers:
        purchases = supplier.purchases.exclude(status=Purchase.Status.CANCELLED)
        invoiced = purchases.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        paid = Decimal("0")
        for p in purchases:
            paid += _payments_total_in_purchase_currency(p)
        balance = invoiced - paid
        if balance <= 0 and not show_all:
            continue
        rows.append({
            "supplier": supplier,
            "count": purchases.count(),
            "invoiced": invoiced,
            "paid": paid,
            "balance": balance,
        })
        total_balance += balance

    rows.sort(key=lambda r: r["balance"], reverse=True)

    return render(request, "procurement/supplier_balance.html", {
        "rows": rows,
        "total_balance": total_balance,
        "show_all": show_all,
    })


def _purchase_form(request, instance: Purchase | None):
    if request.method == "POST":
        form = PurchaseForm(request.POST, instance=instance)
        # Para el formset necesitamos una instancia; si es create, le pasamos
        # una Purchase vacía y la guardamos antes (transacción).
        formset = PurchaseItemFormSet(request.POST, instance=instance or Purchase())
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase = form.save(commit=False)
                if instance is None:
                    purchase.created_by = request.user
                purchase.updated_by = request.user
                purchase.save()

                formset.instance = purchase
                items = formset.save(commit=False)
                for obj in formset.deleted_objects:
                    obj.delete()
                for item in items:
                    item.save()
                # Si quedaron sin items, refrescar el flag.
                if not purchase.items.exists():
                    Purchase.objects.filter(pk=purchase.pk).update(is_itemized=False)
            messages.success(request, "Compra guardada.")
            return redirect("procurement:detail", pk=purchase.pk)
    else:
        form = PurchaseForm(instance=instance)
        formset = PurchaseItemFormSet(instance=instance or Purchase())

    return render(request, "procurement/form.html", {
        "form": form,
        "formset": formset,
        "purchase": instance,
    })
