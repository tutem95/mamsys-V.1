"""Reporte guardado de cruce Presupuesto vs Real.

Cada vez que el usuario "genera" un cruce, se persiste un BudgetVsActualReport
con los totales agregados y el detalle por rubro/task en JSON. Permite ver
la historia de cruces (ej.: cómo evolucionó la varianza mes a mes).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class BudgetVsActualReport(TimestampedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT,
        related_name="budget_actual_reports",
    )
    budget = models.ForeignKey(
        "budgets.Budget", on_delete=models.PROTECT,
        related_name="actual_reports",
    )
    cutoff_date = models.DateField(
        help_text="Fecha de corte: solo se consideran compras y quincenas hasta esta fecha.",
    )
    in_currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="budget_actual_reports",
    )
    rate_type = models.ForeignKey(
        "pricing.ExchangeRateType", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="budget_actual_reports",
    )

    total_planned = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_actual = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    variance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    variance_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))

    data = models.JSONField(default=dict, blank=True,
                             help_text="Breakdown navegable por rubro y tarea.")

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Cruce Presupuesto vs Real"
        verbose_name_plural = "Cruces Presupuesto vs Real"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["budget", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} · P{self.budget.version} @ {self.cutoff_date}"
