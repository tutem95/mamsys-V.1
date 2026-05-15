from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.timezone import localdate, now as tz_now
from django.views.generic import ListView

from apps.permissions.constants import VIEW_TREASURY
from apps.permissions.decorators import PermissionRequiredMixin

from .forms import TreasuryEntryForm
from .models import TreasuryEntry
from .services import compute_account_balances


@method_decorator(login_required, name="dispatch")
class TreasuryEntryListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_TREASURY
    model = TreasuryEntry
    template_name = "treasury/list.html"
    paginate_by = 50
    context_object_name = "entries"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("company", "bank_account__bank", "currency", "project")
        )
        f = self.request.GET
        if f.get("tipo"):
            qs = qs.filter(entry_type=f["tipo"])
        if f.get("categoria"):
            qs = qs.filter(category=f["categoria"])
        if f.get("sociedad"):
            qs = qs.filter(company_id=f["sociedad"])
        if f.get("cuenta"):
            qs = qs.filter(bank_account_id=f["cuenta"])
        if f.get("obra"):
            qs = qs.filter(project_id=f["obra"])
        if f.get("desde"):
            qs = qs.filter(date__gte=f["desde"])
        if f.get("hasta"):
            qs = qs.filter(date__lte=f["hasta"])
        if f.get("conciliado") == "1":
            qs = qs.filter(is_reconciled=True)
        elif f.get("conciliado") == "0":
            qs = qs.filter(is_reconciled=False)
        return qs

    def get_context_data(self, **kwargs):
        from apps.catalog.models import BankAccount
        from apps.companies.models import Company
        from apps.projects.models import Project
        ctx = super().get_context_data(**kwargs)
        f = self.request.GET
        ctx["entry_type_choices"] = TreasuryEntry.EntryType.choices
        ctx["category_choices"] = TreasuryEntry.Category.choices
        ctx["companies"] = Company.objects.filter(active=True).order_by("name")
        ctx["bank_accounts"] = BankAccount.objects.filter(active=True).select_related("bank", "currency").order_by("bank__name")
        ctx["projects"] = Project.objects.filter(is_archived=False).order_by("name")
        ctx["current"] = {k: f.get(k, "") for k in ("tipo", "categoria", "sociedad", "cuenta", "obra", "desde", "hasta", "conciliado")}

        # Totales agregados (solo income/expense — transfer/exchange se omiten).
        income = expense = Decimal("0")
        for e in ctx["entries"]:
            if e.entry_type == TreasuryEntry.EntryType.INCOME:
                income += e.amount
            elif e.entry_type == TreasuryEntry.EntryType.EXPENSE:
                expense += e.amount
        ctx["page_income"] = income
        ctx["page_expense"] = expense
        ctx["page_net"] = income - expense
        return ctx


@login_required
def entry_create(request):
    if request.method == "POST":
        form = TreasuryEntryForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()
            messages.success(request, "Movimiento registrado.")
            return redirect("treasury:list")
    else:
        form = TreasuryEntryForm(initial={"date": localdate()})
    return render(request, "treasury/form.html", {"form": form, "entry": None})


@login_required
def entry_edit(request, pk: int):
    entry = get_object_or_404(TreasuryEntry, pk=pk)
    if request.method == "POST":
        form = TreasuryEntryForm(request.POST, instance=entry)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, "Movimiento actualizado.")
            return redirect("treasury:list")
    else:
        form = TreasuryEntryForm(instance=entry)
    return render(request, "treasury/form.html", {"form": form, "entry": entry})


@login_required
def entry_toggle_reconciled(request, pk: int):
    """POST-only: marca/desmarca como conciliado."""
    if request.method != "POST":
        return redirect("treasury:list")
    entry = get_object_or_404(TreasuryEntry, pk=pk)
    if entry.is_reconciled:
        entry.is_reconciled = False
        entry.reconciled_at = None
        entry.reconciled_by = None
    else:
        entry.is_reconciled = True
        entry.reconciled_at = tz_now()
        entry.reconciled_by = request.user
    entry.save(update_fields=["is_reconciled", "reconciled_at", "reconciled_by", "updated_at"])
    return redirect("treasury:list")


@login_required
def balances(request):
    """Saldos por cuenta bancaria + efectivo."""
    cutoff = request.GET.get("hasta") or None
    company_id = request.GET.get("sociedad") or None
    rows = compute_account_balances(
        cutoff_date=cutoff if cutoff else None,
        company_id=int(company_id) if company_id else None,
    )

    from apps.companies.models import Company
    companies = Company.objects.filter(active=True).order_by("name")
    return render(request, "treasury/balances.html", {
        "rows": rows,
        "cutoff": cutoff,
        "current_company": company_id,
        "companies": companies,
    })
