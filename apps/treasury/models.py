"""Tesorería — movimientos financieros.

TreasuryEntry es el registro único de cualquier movimiento. Lo crea:
- Automáticamente: signals desde PurchasePayment, SocialChargesPayment,
  o PayrollPeriod.status='paid' (TODO).
- Manualmente: para ingresos de clientes, financiamiento, impuestos
  administrativos no vinculados a compras, transferencias internas y
  cambios de moneda.

Soporta multi-moneda con conversión opcional (counterpart_amount/currency
para `currency_exchange`).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class TreasuryEntry(TimestampedModel):
    class EntryType(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Egreso"
        TRANSFER = "transfer", "Transferencia"
        CURRENCY_EXCHANGE = "currency_exchange", "Cambio de moneda"

    class Category(models.TextChoices):
        SUPPLIER_PAYMENT = "supplier_payment", "Pago a proveedor"
        PAYROLL_PAYMENT = "payroll_payment", "Pago de nómina"
        SOCIAL_CHARGES_PAYMENT = "social_charges_payment", "Carga social"
        TAXES = "taxes", "Impuestos"
        FINANCING = "financing", "Financiamiento"
        ADMIN = "admin", "Administrativo"
        CLIENT_PAYMENT = "client_payment", "Cobro cliente"
        CLIENT_ADVANCE = "client_advance", "Anticipo cliente"
        TRANSFER = "transfer", "Transferencia interna"
        CURRENCY_EXCHANGE = "currency_exchange", "Cambio de moneda"
        OTHER = "other", "Otro"

    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)

    date = models.DateField(db_index=True)
    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT,
        related_name="treasury_entries",
    )
    bank_account = models.ForeignKey(
        "catalog.BankAccount", on_delete=models.PROTECT,
        related_name="treasury_entries",
        null=True, blank=True,
        help_text="Si no se carga, el movimiento es en efectivo.",
    )
    counterpart_account = models.ForeignKey(
        "catalog.BankAccount", on_delete=models.PROTECT,
        related_name="counterpart_treasury_entries",
        null=True, blank=True,
        help_text="Cuenta destino para transferencias y cambios de moneda.",
    )

    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="treasury_entries",
    )

    # Para currency_exchange y transfer multi-moneda.
    exchange_rate_used = models.ForeignKey(
        "pricing.ExchangeRate", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    counterpart_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
    )
    counterpart_currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="counterpart_treasury_entries",
        null=True, blank=True,
    )

    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="treasury_entries",
    )

    # Origen automático (signals).
    source_purchase_payment = models.OneToOneField(
        "procurement.PurchasePayment", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="treasury_entry",
    )
    source_social_charges_payment = models.OneToOneField(
        "payroll.SocialChargesPayment", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="treasury_entry",
    )
    source_payroll_period = models.ForeignKey(
        "payroll.PayrollPeriod", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="treasury_entries",
    )

    description = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)

    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reconciled_treasury_entries",
    )

    class Meta:
        verbose_name = "Movimiento financiero"
        verbose_name_plural = "Movimientos financieros"
        ordering = ("-date", "-created_at")
        indexes = [
            models.Index(fields=["company", "-date"]),
            models.Index(fields=["bank_account", "-date"]),
            models.Index(fields=["category", "-date"]),
            models.Index(fields=["project", "-date"]),
            models.Index(fields=["is_reconciled"]),
        ]

    def __str__(self) -> str:
        sign = "+" if self.entry_type == self.EntryType.INCOME else "-"
        return f"{self.date} {sign}{self.amount} {self.currency.code} · {self.get_category_display()}"

    @property
    def signed_amount(self) -> Decimal:
        """Monto con signo: + para income, - para expense.

        Para transfer y currency_exchange dejamos el signo según entry_type
        (los signals los crean con el lado correcto).
        """
        if self.entry_type == self.EntryType.INCOME:
            return self.amount
        if self.entry_type == self.EntryType.EXPENSE:
            return -self.amount
        return self.amount  # transfer/exchange — caso lateral
