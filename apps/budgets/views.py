from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .forms import BudgetForm, BudgetItemFormSet
from .models import Budget
from .services import BudgetApprovalService, BudgetCalculatorService


@method_decorator(login_required, name="dispatch")
class BudgetListView(ListView):
    model = Budget
    template_name = "budgets/list.html"
    paginate_by = 50
    context_object_name = "budgets"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("project", "currency", "approved_by")
        )
        status = self.request.GET.get("estado")
        if status:
            qs = qs.filter(status=status)
        project = self.request.GET.get("obra")
        if project:
            qs = qs.filter(project_id=project)
        return qs

    def get_context_data(self, **kwargs):
        from apps.projects.models import Project
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Budget.Status.choices
        ctx["current_status"] = self.request.GET.get("estado", "")
        ctx["current_project"] = self.request.GET.get("obra", "")
        ctx["projects"] = Project.objects.filter(is_archived=False).order_by("name")
        return ctx


@login_required
def budget_create(request):
    return _budget_form(request, instance=None)


@login_required
def budget_edit(request, pk: int):
    budget = get_object_or_404(Budget, pk=pk)
    if budget.is_locked:
        messages.warning(request, "El presupuesto está cerrado. Cloná una versión nueva para editarlo.")
        return redirect("budgets:detail", pk=budget.pk)
    return _budget_form(request, instance=budget)


def _budget_form(request, instance: Budget | None):
    if request.method == "POST":
        form = BudgetForm(request.POST, instance=instance)
        formset = BudgetItemFormSet(request.POST, instance=instance or Budget())
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                b = form.save(commit=False)
                if instance is None:
                    b.created_by = request.user
                b.updated_by = request.user
                b.save()
                formset.instance = b
                formset.save()
            messages.success(request, "Presupuesto guardado.")
            return redirect("budgets:detail", pk=b.pk)
    else:
        form = BudgetForm(instance=instance)
        formset = BudgetItemFormSet(instance=instance or Budget())

    return render(request, "budgets/form.html", {
        "form": form, "formset": formset, "budget": instance,
    })


@login_required
def budget_detail(request, pk: int):
    budget = get_object_or_404(
        Budget.objects.select_related(
            "project", "currency", "exchange_rate_type", "approved_by",
        ).prefetch_related("items__task__output_unit"),
        pk=pk,
    )
    totals = BudgetCalculatorService.compute(budget)

    # Items con costo (vivo o snapshot).
    items_view = []
    if budget.is_locked:
        for item in budget.items.all():
            items_view.append({
                "item": item,
                "unit_cost": item.unit_cost,
                "total_cost": item.total_cost,
                "materials": item.materials_cost,
                "labor": item.labor_cost,
            })
    else:
        from apps.task_master.services import TaskCostCalculator
        from django.utils.timezone import localdate
        for item in budget.items.all():
            br = TaskCostCalculator.calculate(
                item.task, currency=budget.currency,
                date=budget.pricing_date or localdate(),
                rate_type=budget.exchange_rate_type,
            )
            qty = item.quantity or 0
            items_view.append({
                "item": item,
                "unit_cost": br.total,
                "total_cost": br.total * qty,
                "materials": br.total_materials * qty,
                "labor": br.total_labor * qty,
            })

    return render(request, "budgets/detail.html", {
        "budget": budget,
        "totals": totals,
        "items_view": items_view,
    })


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------

@login_required
def budget_submit(request, pk: int):
    if request.method != "POST":
        return redirect("budgets:detail", pk=pk)
    budget = get_object_or_404(Budget, pk=pk)
    try:
        BudgetApprovalService.submit(budget)
        messages.success(request, "Presupuesto presentado y congelado.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("budgets:detail", pk=budget.pk)


@login_required
def budget_approve(request, pk: int):
    if request.method != "POST":
        return redirect("budgets:detail", pk=pk)
    budget = get_object_or_404(Budget, pk=pk)
    try:
        BudgetApprovalService.approve(budget, request.user)
        messages.success(request, "Presupuesto aprobado. Versiones anteriores marcadas como reemplazadas.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("budgets:detail", pk=budget.pk)


@login_required
def budget_reject(request, pk: int):
    if request.method != "POST":
        return redirect("budgets:detail", pk=pk)
    budget = get_object_or_404(Budget, pk=pk)
    try:
        BudgetApprovalService.reject(budget)
        messages.success(request, "Presupuesto rechazado.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("budgets:detail", pk=budget.pk)


@login_required
def budget_clone(request, pk: int):
    if request.method != "POST":
        return redirect("budgets:detail", pk=pk)
    budget = get_object_or_404(Budget, pk=pk)
    new_budget = BudgetApprovalService.clone_as_new_version(budget, request.user)
    messages.success(request, f"Creada P{new_budget.version} como borrador.")
    return redirect("budgets:detail", pk=new_budget.pk)


@login_required
def budget_pdf(request, pk: int):
    """PDF imprimible del presupuesto (con o sin snapshot)."""
    from decimal import Decimal

    from django.utils.timezone import localdate

    from apps.core.pdf import render_pdf

    budget = get_object_or_404(
        Budget.objects.select_related(
            "project", "project__company", "currency", "exchange_rate_type",
        ).prefetch_related("items__task__output_unit"),
        pk=pk,
    )
    totals = BudgetCalculatorService.compute(budget)

    items_view = []
    if budget.is_locked:
        for item in budget.items.all():
            items_view.append({
                "item": item,
                "unit_cost": item.unit_cost,
                "total_cost": item.total_cost,
            })
    else:
        from apps.task_master.services import TaskCostCalculator
        for item in budget.items.all():
            br = TaskCostCalculator.calculate(
                item.task, currency=budget.currency,
                date=budget.pricing_date or localdate(),
                rate_type=budget.exchange_rate_type,
            )
            qty = item.quantity or Decimal("0")
            items_view.append({
                "item": item,
                "unit_cost": br.total,
                "total_cost": br.total * qty,
            })

    filename = f"presupuesto-{budget.project.name.replace(' ', '_')}-P{budget.version}.pdf"
    return render_pdf(request, "budgets/pdf/budget.html", {
        "budget": budget,
        "totals": totals,
        "items_view": items_view,
        "today": localdate(),
    }, filename)
