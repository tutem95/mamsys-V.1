"""Sociedades (Companies) — razones sociales que pertenecen a una Organization.

Vive en el schema del tenant: cada org tiene sus propias sociedades.
La Organization es el tenant del SaaS; las Companies son sus entidades legales
(S.A., S.R.L., Monotributo, etc.) que facturan, pagan sueldos y firman contratos.

Ejemplos reales del cliente: "PASFAS SA", "350 SRL", "GESTION", "MONOTRIBUTO",
"ÑADEMAETE SA" — todas dentro de la misma Organization.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import TimestampedModel


class Company(TimestampedModel):
    """Sociedad / razón social dentro de un tenant."""

    class IVACondition(models.TextChoices):
        RESPONSABLE_INSCRIPTO = "responsable_inscripto", "Responsable Inscripto"
        MONOTRIBUTO = "monotributo", "Monotributo"
        EXENTO = "exento", "Exento"

    name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField("CUIT", max_length=20, blank=True)

    iva_condition = models.CharField(
        max_length=30,
        choices=IVACondition.choices,
        default=IVACondition.RESPONSABLE_INSCRIPTO,
    )
    iibb_number = models.CharField("Nº IIBB", max_length=30, blank=True)
    fiscal_address = models.CharField(max_length=200, blank=True)

    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sociedad"
        verbose_name_plural = "Sociedades"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["tax_id"], condition=~models.Q(tax_id=""), name="company_unique_tax_id"),
        ]

    def __str__(self) -> str:
        return self.name
