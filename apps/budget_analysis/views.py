from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from apps.permissions.constants import VIEW_BUDGETS
from apps.permissions.decorators import PermissionRequiredMixin

from .forms import GenerateCrossForm
from .models import BudgetVsActualReport
from .services import BudgetActualCrossService, serialize_result


@method_decorator(login_required, name="dispatch")
class ReportListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_BUDGETS
    model = BudgetVsActualReport
    template_name = "budget_analysis/list.html"
    paginate_by = 50
    context_object_name = "reports"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("project", "budget", "in_currency", "generated_by")
        )


@login_required
def cross_generate(request):
    """Form que corre el cruce y opcionalmente lo persiste."""
    if request.method == "POST":
        form = GenerateCrossForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            budget = cd["budget"]
            if budget.project_id != cd["project"].pk:
                messages.error(request, "El presupuesto elegido no pertenece a esa obra.")
            else:
                result = BudgetActualCrossService.compute(
                    budget=budget,
                    cutoff_date=cd["cutoff_date"],
                    currency=cd["in_currency"],
                    rate_type=cd["rate_type"],
                )
                if cd["save_report"]:
                    report = BudgetVsActualReport.objects.create(
                        project=cd["project"],
                        budget=budget,
                        cutoff_date=cd["cutoff_date"],
                        in_currency=cd["in_currency"],
                        rate_type=cd["rate_type"],
                        total_planned=result.total_planned,
                        total_actual=result.total_actual,
                        variance_amount=result.variance_amount,
                        variance_pct=result.variance_pct,
                        data=serialize_result(result),
                        generated_by=request.user,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                    return redirect("budget_analysis:report_detail", pk=report.pk)
                # Sin guardar: renderizar el resultado al vuelo.
                return render(request, "budget_analysis/result_preview.html", {
                    "result": result,
                    "budget": budget,
                })
    else:
        form = GenerateCrossForm()

    return render(request, "budget_analysis/generate.html", {"form": form})


@login_required
def report_detail(request, pk: int):
    report = get_object_or_404(
        BudgetVsActualReport.objects
        .select_related("project", "budget", "in_currency", "generated_by"),
        pk=pk,
    )
    data = report.data or {}
    # Convertir strings serializados a Decimal para que floatformat funcione bien.
    return render(request, "budget_analysis/report_detail.html", {
        "report": report,
        "data": data,
    })
