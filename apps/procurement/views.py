from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from .forms import PurchaseForm, PurchaseItemFormSet
from .models import Purchase, _items_total


@method_decorator(login_required, name="dispatch")
class PurchaseListView(ListView):
    model = Purchase
    template_name = "procurement/list.html"
    paginate_by = 50
    context_object_name = "purchases"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("supplier", "company", "project", "rubro", "original_currency")
        )
        ptype = self.request.GET.get("tipo")
        if ptype in {"obra", "admin", "cadeteria"}:
            qs = qs.filter(purchase_type=ptype)
        status = self.request.GET.get("estado")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_type"] = self.request.GET.get("tipo", "")
        ctx["current_status"] = self.request.GET.get("estado", "")
        ctx["status_choices"] = Purchase.Status.choices
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
        return ctx


@login_required
def purchase_create(request):
    return _purchase_form(request, instance=None)


@login_required
def purchase_edit(request, pk: int):
    purchase = get_object_or_404(Purchase, pk=pk)
    return _purchase_form(request, instance=purchase)


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
