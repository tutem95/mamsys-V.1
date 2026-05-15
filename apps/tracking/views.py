from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from apps.permissions.constants import (
    APPROVE_TASK_SUGGESTIONS,
    VIEW_TRACKING,
)
from apps.permissions.decorators import (
    PermissionRequiredMixin,
    require_permission,
)
from apps.projects.models import Project
from apps.task_master.models import TaskAdjustmentSuggestion

from .models import ProjectExecutionSnapshot, TaskExecution
from .services import (
    TrackingService,
    VarianceAnalyzer,
    approve_suggestion,
    reject_suggestion,
)


@login_required
@require_permission(VIEW_TRACKING)
def project_tracking(request, pk: int):
    """Página de seguimiento de un proyecto: snapshot + tareas + acción regenerar."""
    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST" and request.POST.get("action") == "snapshot":
        TrackingService.snapshot_project(project)
        messages.success(request, "Snapshot generado.")
        return redirect("tracking:project", pk=project.pk)

    snapshots = project.execution_snapshots.select_related("currency").order_by("-snapshot_date")[:30]
    last = snapshots.first() if snapshots else None
    executions = (
        project.task_executions
        .select_related("task__rubro")
        .order_by("task__rubro__name", "task__name")
    )

    return render(request, "tracking/project.html", {
        "project": project,
        "last": last,
        "snapshots": snapshots,
        "executions": executions,
    })


@method_decorator(login_required, name="dispatch")
class SuggestionListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_TRACKING
    model = TaskAdjustmentSuggestion
    template_name = "tracking/suggestions.html"
    paginate_by = 50
    context_object_name = "suggestions"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("task", "component")
            .prefetch_related("based_on_projects")
        )
        status = self.request.GET.get("estado", "pending")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = TaskAdjustmentSuggestion.Status.choices
        ctx["current_status"] = self.request.GET.get("estado", "pending")
        return ctx


@login_required
def scan_variances(request):
    """Corre VarianceAnalyzer y crea sugerencias."""
    if request.method != "POST":
        return redirect("tracking:suggestions")
    findings = VarianceAnalyzer.scan()
    if findings:
        messages.success(request, f"{len(findings)} sugerencia(s) creada/actualizada(s).")
    else:
        messages.info(request, "Sin varianzas significativas detectadas.")
    return redirect("tracking:suggestions")


@login_required
@require_permission(APPROVE_TASK_SUGGESTIONS)
def suggestion_approve(request, pk: int):
    if request.method != "POST":
        return redirect("tracking:suggestions")
    suggestion = get_object_or_404(TaskAdjustmentSuggestion, pk=pk)
    try:
        approve_suggestion(suggestion, request.user)
        messages.success(request, "Sugerencia aprobada. Task.version incrementada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("tracking:suggestions")


@login_required
@require_permission(APPROVE_TASK_SUGGESTIONS)
def suggestion_reject(request, pk: int):
    if request.method != "POST":
        return redirect("tracking:suggestions")
    suggestion = get_object_or_404(TaskAdjustmentSuggestion, pk=pk)
    try:
        reject_suggestion(suggestion, request.user)
        messages.success(request, "Sugerencia rechazada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("tracking:suggestions")
