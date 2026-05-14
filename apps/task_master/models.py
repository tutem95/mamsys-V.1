"""Maestros: Mix (Mezcla) y Task (Tarea), con componentes recursivos.

Estructura:
- Mix: receta de mezcla que combina materiales y/o otras mezclas.
- MixComponent: cada material o sub-mix que la compone, con cantidad por
  unidad de output del Mix padre.
- Task: tarea maestra de obra (ej.: "CERCO DE OBRA EN CHAPA").
- TaskComponent: cada componente con uno de 5 source_types — material,
  labor (un puesto), subcontract, sub_mix o sub_task.

Las recetas son recursivas: un Mix puede usar otro Mix; una Task puede usar
otra Task o un Mix. La validación de ciclos vive en `validators.py`.

Las cantidades son "por unidad de output" del padre — el costo total se
arma vía `services.TaskCostCalculator` que resuelve recursivamente.

`version` incrementa cuando se aprueba una `TaskAdjustmentSuggestion` desde
tracking (Fase 7). Los presupuestos viejos siguen apuntando a snapshots; los
nuevos usan la versión actual.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel


# ---------------------------------------------------------------------------
# Mix (Mezcla)
# ---------------------------------------------------------------------------


class Mix(TimestampedModel):
    """Receta de mezcla.

    Ejemplos: "CONCRETO CON HIDROFUGO", "MORTERO 1:3:5", "PINTURA PARED LATEX".
    """

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=50, blank=True)
    output_unit = models.ForeignKey(
        "catalog.Unit", on_delete=models.PROTECT,
        related_name="mixes_as_output",
        help_text="Unidad del resultado (M2, M3, KG…).",
    )
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Mezcla"
        verbose_name_plural = "Mezclas"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["name"], name="mix_unique_name"),
            models.UniqueConstraint(
                fields=["code"],
                condition=~models.Q(code=""),
                name="mix_unique_code",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class MixComponent(TimestampedModel):
    """Componente de una mezcla: material o sub-mezcla.

    Exactamente uno de `material` / `sub_mix` debe estar lleno.
    `quantity_per_unit` se interpreta por unidad de output del Mix padre.
    """

    mix = models.ForeignKey(Mix, on_delete=models.CASCADE, related_name="components")
    material = models.ForeignKey(
        "catalog.Material", on_delete=models.PROTECT,
        null=True, blank=True, related_name="mix_components",
    )
    sub_mix = models.ForeignKey(
        "Mix", on_delete=models.PROTECT,
        null=True, blank=True, related_name="used_in_mix_components",
    )
    quantity_per_unit = models.DecimalField(max_digits=15, decimal_places=4)
    input_unit = models.ForeignKey(
        "catalog.Unit", on_delete=models.PROTECT,
        related_name="mix_components_as_input",
    )
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Componente de mezcla"
        verbose_name_plural = "Componentes de mezcla"
        ordering = ("mix", "id")

    def __str__(self) -> str:
        target = self.material or self.sub_mix or "?"
        return f"{target} × {self.quantity_per_unit} {self.input_unit}"

    def clean(self):
        has_material = self.material_id is not None
        has_sub_mix = self.sub_mix_id is not None
        if has_material and has_sub_mix:
            raise ValidationError("Un componente no puede ser a la vez material y sub-mezcla.")
        if not has_material and not has_sub_mix:
            raise ValidationError("Cargá un material o una sub-mezcla.")
        if has_sub_mix and self.mix_id and self.sub_mix_id == self.mix_id:
            raise ValidationError("Una mezcla no puede usarse a sí misma.")
        if has_sub_mix and self.mix_id:
            from .validators import detect_mix_cycle
            if detect_mix_cycle(self.mix_id, self.sub_mix_id):
                raise ValidationError(
                    "El sub-mix introduce un ciclo en la receta de mezclas.",
                )


# ---------------------------------------------------------------------------
# Task (Tarea maestra)
# ---------------------------------------------------------------------------


class Task(TimestampedModel):
    """Tarea maestra de obra.

    Ejemplo: "CERCO DE OBRA EN CHAPA" con código "A.1.5".
    """

    code = models.CharField(
        max_length=30, blank=True,
        help_text="Jerárquico opcional (ej.: A.1.5). Auto-generable en futuro.",
    )
    name = models.CharField(max_length=200)
    rubro = models.ForeignKey(
        "catalog.Rubro", on_delete=models.PROTECT, related_name="tasks",
    )
    subrubro = models.ForeignKey(
        "catalog.Subrubro", on_delete=models.PROTECT,
        null=True, blank=True, related_name="tasks",
    )
    output_unit = models.ForeignKey(
        "catalog.Unit", on_delete=models.PROTECT,
        related_name="tasks_as_output",
        help_text="Unidad de la Tarea (UT).",
    )
    description = models.TextField("Detalle", blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ("code", "name")
        constraints = [
            models.UniqueConstraint(fields=["name"], name="task_unique_name"),
            models.UniqueConstraint(
                fields=["code"], condition=~models.Q(code=""), name="task_unique_code",
            ),
        ]

    def __str__(self) -> str:
        if self.code:
            return f"{self.code} · {self.name}"
        return self.name


class TaskComponent(TimestampedModel):
    """Componente de una tarea.

    `source_type` define cuál FK está poblada (los otros 4 quedan None).
    El `classification` (materials / labor) se almacena para que los reportes
    no tengan que mirar `source_type` en cada agregación.
    """

    class SourceType(models.TextChoices):
        MATERIAL = "material", "Material"
        LABOR = "labor", "Mano de obra"
        SUBCONTRACT = "subcontract", "Subcontrato"
        SUB_MIX = "sub_mix", "Sub-mezcla"
        SUB_TASK = "sub_task", "Sub-tarea"

    class Classification(models.TextChoices):
        MATERIALS = "materials", "Materiales"
        LABOR = "labor", "Mano de obra"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="components")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)

    # Exactamente uno según source_type:
    material = models.ForeignKey(
        "catalog.Material", on_delete=models.PROTECT,
        null=True, blank=True, related_name="task_components",
    )
    position = models.ForeignKey(
        "catalog.Position", on_delete=models.PROTECT,
        null=True, blank=True, related_name="task_components",
    )
    subcontract = models.ForeignKey(
        "catalog.Subcontract", on_delete=models.PROTECT,
        null=True, blank=True, related_name="task_components",
    )
    sub_mix = models.ForeignKey(
        Mix, on_delete=models.PROTECT,
        null=True, blank=True, related_name="task_components_as_sub_mix",
    )
    sub_task = models.ForeignKey(
        Task, on_delete=models.PROTECT,
        null=True, blank=True, related_name="used_in_task_components",
    )

    classification = models.CharField(
        max_length=20, choices=Classification.choices, default=Classification.MATERIALS,
    )
    quantity_per_unit = models.DecimalField(max_digits=15, decimal_places=4)
    input_unit = models.ForeignKey(
        "catalog.Unit", on_delete=models.PROTECT,
        related_name="task_components_as_input",
    )
    detail = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Componente de tarea"
        verbose_name_plural = "Componentes de tarea"
        ordering = ("task", "id")

    _SOURCE_FIELD_MAP = {
        SourceType.MATERIAL: "material_id",
        SourceType.LABOR: "position_id",
        SourceType.SUBCONTRACT: "subcontract_id",
        SourceType.SUB_MIX: "sub_mix_id",
        SourceType.SUB_TASK: "sub_task_id",
    }

    def __str__(self) -> str:
        target = (
            self.material or self.position or self.subcontract
            or self.sub_mix or self.sub_task or "?"
        )
        return f"{target} × {self.quantity_per_unit} {self.input_unit}"

    def clean(self):
        required = self._SOURCE_FIELD_MAP[self.source_type]
        # Exactamente el campo correspondiente al source_type debe estar lleno.
        all_fks = list(self._SOURCE_FIELD_MAP.values())
        for field in all_fks:
            value = getattr(self, field)
            if field == required:
                if value is None:
                    raise ValidationError(
                        f"Cargá un {self.get_source_type_display()}.",
                    )
            else:
                if value is not None:
                    raise ValidationError(
                        f"El source_type {self.source_type} no debería tener {field} cargado.",
                    )
        # Auto-set classification.
        if self.source_type == self.SourceType.LABOR:
            self.classification = self.Classification.LABOR
        elif self.source_type in {self.SourceType.MATERIAL, self.SourceType.SUBCONTRACT, self.SourceType.SUB_MIX}:
            self.classification = self.Classification.MATERIALS
        # Para sub_task no forzamos: hereda lo que decida el editor.

        # Anti-ciclo en sub_task.
        if self.source_type == self.SourceType.SUB_TASK and self.task_id:
            if self.sub_task_id == self.task_id:
                raise ValidationError("Una tarea no puede usarse a sí misma.")
            from .validators import detect_task_cycle
            if detect_task_cycle(self.task_id, self.sub_task_id):
                raise ValidationError(
                    "La sub-tarea introduce un ciclo en la receta.",
                )


# ---------------------------------------------------------------------------
# Sugerencias automáticas (placeholder hasta Fase 7)
# ---------------------------------------------------------------------------


class TaskAdjustmentSuggestion(TimestampedModel):
    """Sugerencia automática generada por tracking cuando detecta varianzas.

    Modelo base ya disponible para que tracking (Fase 7) escriba en él.
    El flujo de aprobación que incrementa Task.version se implementa cuando
    haya datos reales con qué comparar.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="adjustment_suggestions")
    component = models.ForeignKey(
        TaskComponent, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="adjustment_suggestions",
    )
    current_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    suggested_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    based_on_projects = models.ManyToManyField(
        "projects.Project", blank=True, related_name="task_adjustment_suggestions",
    )
    sample_size = models.PositiveIntegerField(default=0)
    variance_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sugerencia de ajuste"
        verbose_name_plural = "Sugerencias de ajuste"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Sugerencia {self.task.name}: {self.current_quantity} → {self.suggested_quantity}"
