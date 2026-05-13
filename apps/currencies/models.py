"""Monedas globales del SaaS.

Vive en el schema `public` (SHARED): una moneda es la misma para todos los
tenants (USD es USD en cualquier organización). ExchangeRateType, en cambio,
es per-tenant: cada organización define sus tipos de cotización (BNA, CCL,
Nocito, 70/30) y sus cotizaciones diarias.
"""

from __future__ import annotations

from django.db import models


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, help_text="ISO-4217: ARS, USD, EUR…")
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code
