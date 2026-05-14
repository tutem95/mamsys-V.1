"""Presupuestos.

Un Budget pertenece a un Project y tiene una version (P1, P2, P3...). Cuando
cambia de estado a `submitted` o `approved`, se congela:
- pricing_date, exchange_rate_type, exchange_rate_value
- por cada BudgetItem: unit_cost, total_cost, breakdown materiales/labor/
  subcontratos, recipe_snapshot (JSON con la receta completa del Task).

Después del snapshot, los cambios en el catálogo (precios, recetas) NO afectan
al presupuesto. Para "qué pasaría con los nuevos precios" → nueva version.

Cuando una version posterior se aprueba, la anterior aprobada pasa a
`superseded` automáticamente.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class Budget(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SUBMITTED = "submitted", "Presentado"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        SUPERSEDED = "superseded", "Reemplazado"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT,
        related_name="budgets",
    )
    name = models.CharField(max_length=160, blank=True)
    version = models.PositiveIntegerField(
        default=1, help_text="Versión: 1 = P1, 2 = P2, etc.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    # Snapshot al cerrar (submitted / approved).
    pricing_date = models.DateField(
        null=True, blank=True,
        help_text="Fecha de los precios usados al congelar.",
    )
    exchange_rate_type = models.ForeignKey(
        "pricing.ExchangeRateType", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="budgets",
    )
    exchange_rate_value = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True,
    )
    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="budgets",
    )

    # Totales (snapshot — se llenan al cerrar; durante draft se calculan en vivo).
    total_in_ars = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_in_usd = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    materials_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    subcontracts_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    margin_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0"),
        help_text="Markup que se suma al subtotal para llegar al total con margen.",
    )
    total_with_margin = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    # Aprobación
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="approved_budgets",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"
        ordering = ("-project", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version"],
                name="budget_unique_version_per_project",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} · P{self.version}"

    @property
    def is_locked(self) -> bool:
        """True si el snapshot ya está congelado."""
        return self.status in {
            self.Status.SUBMITTED,
            self.Status.APPROVED,
            self.Status.REJECTED,
            self.Status.SUPERSEDED,
        }


class BudgetItem(TimestampedModel):
    """Ítem del presupuesto: una Task del maestro con cantidad.

    Durante draft, el unit_cost se calcula al vuelo. Al cerrar (Turno snapshot)
    se congelan unit_cost, total_cost, los desgloses y recipe_snapshot.
    """

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="items")
    task = models.ForeignKey(
        "task_master.Task", on_delete=models.PROTECT,
        related_name="budget_items",
    )
    task_version = models.PositiveIntegerField(
        default=1,
        help_text="Versión del Task usada al congelar.",
    )

    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    # Snapshot de desglose
    materials_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    subcontracts_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    # Receta congelada — sirve para reportes históricos aunque el maestro cambie.
    recipe_snapshot = models.JSONField(default=dict, blank=True)

    order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Ítem de presupuesto"
        verbose_name_plural = "Ítems de presupuesto"
        ordering = ("budget", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["budget", "task"],
                name="budgetitem_unique_task_per_budget",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.task.name} × {self.quantity}"
