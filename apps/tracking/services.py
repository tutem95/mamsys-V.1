"""Servicios de seguimiento.

- TrackingService.snapshot_project(): calcula y persiste un
  ProjectExecutionSnapshot al día.
- TrackingService.update_task_executions(): para cada Task usada en
  el proyecto, calcula actual_quantity y actual_cost desde
  PurchaseItem + PayrollAllocation. Cruza con planned del último
  Budget approved cuando existe.
- VarianceAnalyzer.scan(): analiza TaskExecutions con varianza > umbral
  y genera TaskAdjustmentSuggestion para revisión humana.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils.timezone import localdate, now as tz_now


@dataclass
class SnapshotResult:
    snapshot_id: int
    project_name: str
    snapshot_date: _date
    total_cost: Decimal
    total_materials: Decimal
    total_labor: Decimal
    total_subcontracts: Decimal
    total_cs_real: Decimal
    total_cs_estimated: Decimal


class TrackingService:
    """Calcula snapshots y ejecuciones por tarea."""

    @classmethod
    def snapshot_project(
        cls, project, snapshot_date: _date | None = None, currency=None,
    ):
        """Crea o actualiza el snapshot del día con costos agregados."""
        from apps.currencies.models import Currency
        from apps.payroll.models import PayrollAllocation
        from apps.procurement.models import Purchase, PurchaseItem

        from .models import ProjectExecutionSnapshot

        if snapshot_date is None:
            snapshot_date = localdate()
        if currency is None:
            currency = Currency.objects.get(code="ARS")

        # Compras (no canceladas) hasta la fecha de snapshot.
        purchases = (
            Purchase.objects
            .filter(project=project, invoice_date__lte=snapshot_date)
            .exclude(status=Purchase.Status.CANCELLED)
            .select_related("rubro")
            .prefetch_related("items")
        )

        materials = Decimal("0")
        subcontracts = Decimal("0")
        per_rubro: dict[int, dict] = {}
        per_task: dict[int, Decimal] = {}

        for p in purchases:
            total = p.total_amount or Decimal("0")
            bucket_subcontract = bool(p.is_subcontract)
            # Heurística rubro = cabecera.
            rid = p.rubro_id
            per_rubro.setdefault(rid, {"name": p.rubro.name, "amount": Decimal("0")})
            per_rubro[rid]["amount"] += total
            if bucket_subcontract:
                subcontracts += total
            else:
                materials += total
            # Por task — si los ítems tienen task_id, prorratear.
            items = list(p.items.all())
            items_subtotal = sum((it.total or Decimal("0")) for it in items)
            if items_subtotal > 0:
                ratio = total / items_subtotal
                for it in items:
                    if it.task_id:
                        per_task[it.task_id] = per_task.get(it.task_id, Decimal("0")) + (it.total * ratio)

        # Nómina hasta la fecha del snapshot.
        allocations = (
            PayrollAllocation.objects
            .filter(
                project=project,
                payroll_entry__payroll_period__end_date__lte=snapshot_date,
            )
            .select_related("payroll_entry")
        )

        labor_internal = Decimal("0")
        cs_real = Decimal("0")
        cs_estimated = Decimal("0")
        for alloc in allocations:
            labor_internal += alloc.net_amount or Decimal("0")
            if alloc.social_charges_status == "real":
                cs_real += alloc.social_charges_amount or Decimal("0")
            else:
                cs_estimated += alloc.social_charges_amount or Decimal("0")
            if alloc.task_id:
                per_task[alloc.task_id] = per_task.get(alloc.task_id, Decimal("0")) + (
                    (alloc.net_amount or Decimal("0")) + (alloc.social_charges_amount or Decimal("0"))
                )

        total_cost = materials + subcontracts + labor_internal + cs_real + cs_estimated

        breakdown = {
            "rubros": [
                {"id": rid, "name": r["name"], "amount": str(r["amount"].quantize(Decimal("0.01")))}
                for rid, r in per_rubro.items()
            ],
            "tasks": [
                {"id": tid, "amount": str(amount.quantize(Decimal("0.01")))}
                for tid, amount in per_task.items()
            ],
        }

        snapshot, _ = ProjectExecutionSnapshot.objects.update_or_create(
            project=project, snapshot_date=snapshot_date,
            defaults={
                "currency": currency,
                "total_materials_cost": materials.quantize(Decimal("0.01")),
                "total_labor_internal_cost": labor_internal.quantize(Decimal("0.01")),
                "total_labor_subcontract_cost": subcontracts.quantize(Decimal("0.01")),
                "total_social_charges_real": cs_real.quantize(Decimal("0.01")),
                "total_social_charges_estimated": cs_estimated.quantize(Decimal("0.01")),
                "total_cost": total_cost.quantize(Decimal("0.01")),
                "breakdown": breakdown,
            },
        )

        # Actualizar TaskExecutions con la info de planning vs actual.
        cls.update_task_executions(project, per_task)

        return SnapshotResult(
            snapshot_id=snapshot.pk,
            project_name=project.name,
            snapshot_date=snapshot_date,
            total_cost=snapshot.total_cost,
            total_materials=snapshot.total_materials_cost,
            total_labor=snapshot.total_labor_internal_cost,
            total_subcontracts=snapshot.total_labor_subcontract_cost,
            total_cs_real=snapshot.total_social_charges_real,
            total_cs_estimated=snapshot.total_social_charges_estimated,
        )

    @classmethod
    def update_task_executions(cls, project, per_task_actual: dict[int, Decimal] | None = None):
        """Actualiza TaskExecutions a partir del último Budget approved.

        Si `per_task_actual` es None, recalcula desde scratch.
        """
        from apps.budgets.models import Budget
        from apps.task_master.models import Task

        from .models import TaskExecution

        # Buscar el budget approved más reciente del proyecto.
        budget = (
            Budget.objects.filter(project=project, status=Budget.Status.APPROVED)
            .order_by("-version").first()
        )

        if per_task_actual is None:
            per_task_actual = cls._compute_per_task_actual(project)

        # Tareas con planificado.
        planned_tasks: dict[int, dict] = {}
        if budget is not None:
            for item in budget.items.select_related("task"):
                planned_tasks[item.task_id] = {
                    "planned_quantity": item.quantity or Decimal("0"),
                    "planned_cost": item.total_cost or Decimal("0"),
                    "task_version": item.task_version or 1,
                }

        # Unir tasks planificadas + tasks con actual.
        all_task_ids = set(planned_tasks.keys()) | set(per_task_actual.keys())
        for tid in all_task_ids:
            planned = planned_tasks.get(tid, {})
            actual_cost = per_task_actual.get(tid, Decimal("0"))
            task = Task.objects.filter(pk=tid).first()
            if task is None:
                continue
            te, _ = TaskExecution.objects.update_or_create(
                project=project, task=task,
                defaults={
                    "task_version": planned.get("task_version", task.version),
                    "planned_quantity": planned.get("planned_quantity", Decimal("0")),
                    "planned_cost": planned.get("planned_cost", Decimal("0")),
                    "actual_cost": actual_cost.quantize(Decimal("0.01")),
                    "last_computed_at": tz_now(),
                },
            )

    @classmethod
    def _compute_per_task_actual(cls, project) -> dict[int, Decimal]:
        from apps.payroll.models import PayrollAllocation
        from apps.procurement.models import PurchaseItem

        result: dict[int, Decimal] = {}

        items = (
            PurchaseItem.objects
            .filter(
                purchase__project=project,
                task_id__isnull=False,
            )
            .exclude(purchase__status="cancelled")
        )
        for it in items:
            result[it.task_id] = result.get(it.task_id, Decimal("0")) + (it.total or Decimal("0"))

        allocs = (
            PayrollAllocation.objects
            .filter(
                project=project,
                task_id__isnull=False,
            )
        )
        for a in allocs:
            inc = (a.net_amount or Decimal("0")) + (a.social_charges_amount or Decimal("0"))
            result[a.task_id] = result.get(a.task_id, Decimal("0")) + inc

        return result


# ---------------------------------------------------------------------------
# VarianceAnalyzer
# ---------------------------------------------------------------------------


@dataclass
class VarianceFinding:
    task_id: int
    task_name: str
    projects_sample: list[int]
    sample_size: int
    avg_variance_pct: Decimal


class VarianceAnalyzer:
    """Detecta tareas cuyo costo real se aparta sistemáticamente del planificado.

    Heurística mínima viable:
    - Solo considera TaskExecution con planned_cost > 0.
    - Una task es "sospechosa" si en ≥ `min_samples` proyectos su varianza %
      promedia > `threshold_pct`.
    - Por cada hallazgo, crea o actualiza una TaskAdjustmentSuggestion pending.
    """

    @classmethod
    def scan(cls, threshold_pct: Decimal = Decimal("15"), min_samples: int = 3) -> list[VarianceFinding]:
        from apps.task_master.models import Task, TaskAdjustmentSuggestion

        from .models import TaskExecution

        executions = (
            TaskExecution.objects
            .filter(planned_cost__gt=0)
            .select_related("task", "project")
        )

        # Agrupar por task.
        by_task: dict[int, list[TaskExecution]] = {}
        for te in executions:
            by_task.setdefault(te.task_id, []).append(te)

        findings: list[VarianceFinding] = []
        for tid, list_te in by_task.items():
            if len(list_te) < min_samples:
                continue
            avg_var = sum((te.variance_pct for te in list_te), Decimal("0")) / len(list_te)
            if abs(avg_var) < threshold_pct:
                continue
            task = list_te[0].task
            finding = VarianceFinding(
                task_id=tid,
                task_name=task.name,
                projects_sample=[te.project_id for te in list_te],
                sample_size=len(list_te),
                avg_variance_pct=avg_var.quantize(Decimal("0.01")),
            )
            findings.append(finding)

            # Crear / actualizar sugerencia.
            suggestion, _ = TaskAdjustmentSuggestion.objects.update_or_create(
                task=task,
                status=TaskAdjustmentSuggestion.Status.PENDING,
                defaults={
                    "current_quantity": Decimal("1"),  # placeholder — el ajuste real depende del componente.
                    "suggested_quantity": Decimal("1") * (Decimal("1") + avg_var / Decimal("100")),
                    "sample_size": len(list_te),
                    "variance_pct": finding.avg_variance_pct,
                    "notes": (
                        f"Varianza promedio detectada en {len(list_te)} obras "
                        f"({finding.avg_variance_pct}%). Revisar receta y ajustar componentes."
                    ),
                },
            )
            suggestion.based_on_projects.set(set(finding.projects_sample))

        return findings


def approve_suggestion(suggestion, user) -> None:
    """Aprueba una sugerencia: incrementa Task.version y marca aprobada.

    El ajuste exacto en componentes queda como TODO para una pasada con UI
    de "editar componente" pre-aprobación; por ahora solo registramos la
    aprobación y bumpeamos la versión.
    """
    from apps.task_master.models import TaskAdjustmentSuggestion

    if suggestion.status != TaskAdjustmentSuggestion.Status.PENDING:
        raise ValueError("Solo se aprueban sugerencias pendientes.")
    task = suggestion.task
    task.version += 1
    task.save(update_fields=["version", "updated_at"])

    suggestion.status = TaskAdjustmentSuggestion.Status.APPROVED
    suggestion.reviewed_at = tz_now()
    suggestion.save(update_fields=["status", "reviewed_at", "updated_at"])


def reject_suggestion(suggestion, user) -> None:
    from apps.task_master.models import TaskAdjustmentSuggestion

    if suggestion.status != TaskAdjustmentSuggestion.Status.PENDING:
        raise ValueError("Solo se rechazan sugerencias pendientes.")
    suggestion.status = TaskAdjustmentSuggestion.Status.REJECTED
    suggestion.reviewed_at = tz_now()
    suggestion.save(update_fields=["status", "reviewed_at", "updated_at"])
