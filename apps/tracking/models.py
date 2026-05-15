"""Seguimiento de obras.

ProjectExecutionSnapshot: foto del estado de una obra a una fecha. Se calcula
desde procurement + payroll. Lo guardamos para historial (gráficos de
evolución, comparaciones mes a mes).

TaskExecution: ejecución real de una task en una obra. Permite cruzar
contra el snapshot del Budget. Lo poblamos cuando el usuario "marca"
manualmente o cuando genera un análisis de varianza.

ProjectForecast: previsión simple a futuro. Modelo base; las heurísticas
de forecast se afinarán cuando haya historia.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.core.models import TimestampedModel


class ProjectExecutionSnapshot(TimestampedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="execution_snapshots",
    )
    snapshot_date = models.DateField(db_index=True)

    total_materials_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_labor_internal_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_labor_subcontract_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_social_charges_real = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_social_charges_estimated = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="execution_snapshots",
    )

    breakdown = models.JSONField(
        default=dict, blank=True,
        help_text="Desglose por rubro/subrubro/task (JSON serializable).",
    )

    class Meta:
        verbose_name = "Snapshot de obra"
        verbose_name_plural = "Snapshots de obra"
        ordering = ("-snapshot_date", "-created_at")
        indexes = [
            models.Index(fields=["project", "-snapshot_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "snapshot_date"],
                name="snapshot_unique_per_project_per_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} @ {self.snapshot_date}"


class TaskExecution(TimestampedModel):
    """Ejecución real de una task en una obra puntual.

    `actual_quantity` y `actual_cost` se acumulan de PurchaseItems y
    PayrollAllocations que tengan `task_id` apuntando a esta task.
    """

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "No iniciada"
        IN_PROGRESS = "in_progress", "En curso"
        COMPLETED = "completed", "Completada"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="task_executions",
    )
    task = models.ForeignKey(
        "task_master.Task", on_delete=models.PROTECT,
        related_name="executions",
    )
    task_version = models.PositiveIntegerField(default=1)

    planned_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    actual_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    planned_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    actual_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    completion_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)

    last_computed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ejecución de tarea"
        verbose_name_plural = "Ejecuciones de tarea"
        ordering = ("project", "task")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "task"],
                name="taskexecution_unique_task_per_project",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.task.name} @ {self.project.name}"

    @property
    def variance_amount(self) -> Decimal:
        return (self.actual_cost - self.planned_cost).quantize(Decimal("0.01"))

    @property
    def variance_pct(self) -> Decimal:
        if self.planned_cost == 0:
            return Decimal("0") if self.actual_cost == 0 else Decimal("100")
        return ((self.actual_cost - self.planned_cost) / self.planned_cost * Decimal("100")).quantize(Decimal("0.01"))


class ProjectForecast(TimestampedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="forecasts",
    )
    forecast_date = models.DateField()
    forecasted_total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    forecasted_completion_date = models.DateField(null=True, blank=True)
    forecasted_social_charges = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Previsión"
        verbose_name_plural = "Previsiones"
        ordering = ("-forecast_date",)

    def __str__(self) -> str:
        return f"Previsión {self.project.name} @ {self.forecast_date}"
