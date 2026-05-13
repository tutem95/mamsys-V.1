"""Tipos de cotización y cotizaciones por fecha.

Vive en TENANT: cada organización configura sus propios tipos (BNA, CCL,
Nocito, 70/30) y carga las cotizaciones diarias que usa para conversión.

La FK a Currency apunta al schema `public` (SHARED). django-tenants resuelve
la referencia vía search_path.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from django.db import models

from apps.core.models import TimestampedModel


class ExchangeRateType(TimestampedModel):
    """Tipo de cotización: BNA, CCL, Nocito, 70/30, etc."""

    class CalculationType(models.TextChoices):
        MANUAL = "manual", "Manual"
        WEIGHTED = "weighted_combination", "Combinación ponderada"

    name = models.CharField(max_length=50)
    currency_from = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="rate_types_from",
        help_text="Moneda de origen del par (ej.: USD).",
    )
    currency_to = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="rate_types_to",
        help_text="Moneda de destino del par (ej.: ARS).",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Si está marcado, se usa cuando una operación no especifica tipo.",
    )
    calculation_type = models.CharField(
        max_length=30,
        choices=CalculationType.choices,
        default=CalculationType.MANUAL,
    )
    combination_formula = models.JSONField(
        null=True,
        blank=True,
        help_text="Solo para tipos ponderados. Ej: {\"BNA\": 0.7, \"CCL\": 0.3}.",
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tipo de cotización"
        verbose_name_plural = "Tipos de cotización"
        ordering = ("-is_default", "name")
        constraints = [
            models.UniqueConstraint(fields=["name"], name="ratetype_unique_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency_from.code}→{self.currency_to.code})"


class ExchangeRate(TimestampedModel):
    """Cotización de un tipo en una fecha puntual."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORTED = "imported", "Importada"
        CALCULATED = "calculated", "Calculada"

    rate_type = models.ForeignKey(
        ExchangeRateType,
        on_delete=models.CASCADE,
        related_name="rates",
    )
    date = models.DateField(db_index=True)
    rate = models.DecimalField(max_digits=15, decimal_places=4)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=["rate_type", "date"], name="rate_unique_per_type_per_date"),
        ]
        indexes = [
            models.Index(fields=["rate_type", "-date"]),
        ]

    def __str__(self) -> str:
        return f"{self.rate_type.name} @ {self.date}: {self.rate}"

    def to_amount(self, amount: Decimal | float | int) -> Decimal:
        """Convierte un monto en `currency_from` a `currency_to` usando esta cotización."""
        return Decimal(amount) * self.rate
