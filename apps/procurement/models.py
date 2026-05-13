"""Compras (KPS): cabecera + ítems opcionales.

Una Compra puede ser:
- De obra: imputada a un Project. Propiedad de Gestión/Área Técnica.
- Administrativa o de cadetería: gastos generales. Propiedad de Tesorería.
- Subcontrato (is_subcontract=True): la compra entera representa un servicio
  contratado. En ese caso los ítems referencian Subcontract en vez de Material.

Cualquier compra puede abrirse en ítems o quedarse solo en la cabecera. La
suma de ítems debe cuadrar con el subtotal sin IVA, pero el sistema no
bloquea — solo muestra warning (ver §6.1 del SPEC: "Si hay diferencia entre
suma de ítems y cabecera → warning visible").

Pagos (PurchasePayment) y signal que popula Price van en el siguiente turno.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel


class Purchase(TimestampedModel):
    """Cabecera de una compra/factura."""

    class PurchaseType(models.TextChoices):
        OBRA = "obra", "De obra"
        ADMIN = "admin", "Administrativa"
        CADETERIA = "cadeteria", "Cadetería"

    class DocumentType(models.TextChoices):
        FACTURA_A = "factura_a", "Factura A"
        FACTURA_B = "factura_b", "Factura B"
        FACTURA_C = "factura_c", "Factura C"
        PRESUPUESTO = "presupuesto", "Presupuesto"
        REMITO = "remito", "Remito"
        TICKET = "ticket", "Ticket"
        OTRO = "otro", "Otro"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        TO_PAY = "to_pay", "A pagar"
        PAID_PARTIAL = "paid_partial", "Pagada parcial"
        PAID = "paid", "Pagada"
        CANCELLED = "cancelled", "Cancelada"

    # ---- Identificación / clasificación ----
    purchase_type = models.CharField(max_length=20, choices=PurchaseType.choices, default=PurchaseType.OBRA)
    document_type = models.CharField(max_length=20, choices=DocumentType.choices, default=DocumentType.FACTURA_A)
    document_number = models.CharField("Nº comprobante", max_length=50, blank=True)
    invoice_date = models.DateField()

    is_subcontract = models.BooleanField(
        default=False,
        help_text="Si es True, la compra entera es un subcontrato. Los ítems se cargan contra Subcontracts.",
    )
    # Flag automático: True cuando hay al menos un PurchaseItem.
    is_itemized = models.BooleanField(default=False, editable=False)

    # ---- Proveedor y sociedad ----
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="purchases",
    )
    supplier_email = models.EmailField(blank=True, help_text="Override del mail del catálogo.")
    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="purchases",
    )

    # ---- Imputación principal (cabecera) ----
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT,
        related_name="purchases", null=True, blank=True,
        help_text="Obligatorio si purchase_type='obra'.",
    )
    rubro = models.ForeignKey(
        "catalog.Rubro", on_delete=models.PROTECT, related_name="purchases",
    )
    subrubro = models.ForeignKey(
        "catalog.Subrubro", on_delete=models.PROTECT,
        related_name="purchases", null=True, blank=True,
    )
    business_component = models.ForeignKey(
        "catalog.BusinessComponent", on_delete=models.PROTECT,
        related_name="purchases", null=True, blank=True,
    )
    detail = models.CharField(max_length=300, blank=True, help_text="Descripción libre.")
    main_item_description = models.CharField(
        max_length=300, blank=True,
        help_text="Solo si no se abre en ítems.",
    )

    # ---- Montos en moneda original ----
    original_currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="purchases",
    )
    amount_without_tax = models.DecimalField("Monto sin IVA", max_digits=15, decimal_places=2, default=Decimal("0"))
    iva_21 = models.DecimalField("IVA 21%", max_digits=15, decimal_places=2, default=Decimal("0"))
    iva_10_5 = models.DecimalField("IVA 10,5%", max_digits=15, decimal_places=2, default=Decimal("0"))
    perc_iibb = models.DecimalField("Percepción IIBB", max_digits=15, decimal_places=2, default=Decimal("0"))
    total_amount = models.DecimalField("Monto total", max_digits=15, decimal_places=2, default=Decimal("0"))

    # ---- Conversión (cache poblada por servicio/save) ----
    exchange_rate_used = models.ForeignKey(
        "pricing.ExchangeRate", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    total_in_ars = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_in_usd_oficial = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_in_usd_ccl = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # ---- Pago / vencimiento ----
    payment_method = models.CharField(max_length=80, blank=True)
    week_to_pay = models.CharField(max_length=30, blank=True, help_text="Ej: '2026-W20'.")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # TODO(warehouse): Warehouse aún no existe como modelo (necesita Employee
    # como keeper, llega en Fase 5). Cuando exista, agregar FK aquí.

    notes = models.TextField("Observaciones", blank=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ("-invoice_date", "-created_at")
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["project", "-invoice_date"]),
            models.Index(fields=["supplier", "-invoice_date"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self) -> str:
        doc = f"{self.get_document_type_display()} {self.document_number}".strip()
        return f"{doc} · {self.supplier}".strip(" ·")

    def clean(self):
        if self.purchase_type == self.PurchaseType.OBRA and self.project_id is None:
            raise ValidationError({"project": "Una compra de obra requiere proyecto."})

    def save(self, *args, **kwargs):
        # Si no se ingresó total_amount, lo armamos.
        if not self.total_amount:
            self.total_amount = (
                (self.amount_without_tax or 0)
                + (self.iva_21 or 0) + (self.iva_10_5 or 0)
                + (self.perc_iibb or 0)
            )
        super().save(*args, **kwargs)


class PurchaseItem(TimestampedModel):
    """Ítem de una compra: material o subcontrato según `purchase.is_subcontract`.

    Cuando la compra está confirmada (status != draft), un signal de Fase 4
    Turno B creará automáticamente un `pricing.Price` con el unit_price.
    """

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    item_description = models.CharField(max_length=300, blank=True)

    material = models.ForeignKey(
        "catalog.Material", on_delete=models.PROTECT,
        null=True, blank=True, related_name="purchase_items",
    )
    subcontract = models.ForeignKey(
        "catalog.Subcontract", on_delete=models.PROTECT,
        null=True, blank=True, related_name="purchase_items",
    )

    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="purchase_items")
    unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))

    # Sub-imputación opcional
    subrubro = models.ForeignKey(
        "catalog.Subrubro", on_delete=models.PROTECT,
        null=True, blank=True, related_name="purchase_items",
    )
    tracking_category = models.ForeignKey(
        "catalog.TrackingCategory", on_delete=models.PROTECT,
        null=True, blank=True, related_name="purchase_items",
    )
    # task FK queda como placeholder hasta Fase 6 (task_master).
    task_id = models.PositiveIntegerField(null=True, blank=True)

    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Ítem de compra"
        verbose_name_plural = "Ítems de compra"
        ordering = ("purchase", "id")

    def __str__(self) -> str:
        target = self.material or self.subcontract or "ítem"
        return f"{target} × {self.quantity}"

    def clean(self):
        # Exactamente uno de material/subcontract debe estar lleno, y debe
        # coincidir con purchase.is_subcontract.
        has_material = self.material_id is not None
        has_subcontract = self.subcontract_id is not None
        if has_material and has_subcontract:
            raise ValidationError("Un ítem no puede ser a la vez material y subcontrato.")
        if not has_material and not has_subcontract:
            raise ValidationError("Cargá un material o un subcontrato.")
        if self.purchase_id:
            # Cuando se valida individual (no en formset) tenemos la compra.
            if self.purchase.is_subcontract and has_material:
                raise ValidationError("La compra es subcontrato; cargá un Subcontract en vez de Material.")
            if not self.purchase.is_subcontract and has_subcontract:
                raise ValidationError("La compra no es subcontrato; cargá un Material.")

    def save(self, *args, **kwargs):
        # Recalcular total a partir de quantity * unit_price (2 decimales).
        self.total = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
        # Mantener is_itemized en la cabecera coherente.
        if not self.purchase.is_itemized:
            Purchase.objects.filter(pk=self.purchase_id).update(is_itemized=True)


def _items_total(purchase: Purchase) -> Decimal:
    """Suma del total de los items de una compra. Para mostrar warnings."""
    return purchase.items.aggregate(total=models.Sum("total"))["total"] or Decimal("0")


class PurchasePayment(TimestampedModel):
    """Pago (parcial o total) contra una compra.

    La suma de pagos de una compra (convertidos a la moneda de la compra
    cuando corresponda) determina si el status pasa a paid_partial o paid.
    """

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="purchase_payments",
    )
    exchange_rate_used = models.ForeignKey(
        "pricing.ExchangeRate", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
        help_text="Solo si la moneda del pago difiere de la moneda de la compra.",
    )
    # TODO(bank_account): Cuenta bancaria (Fase 2 + Fase 10 — depende de Bank/Company/Currency).
    payment_method = models.CharField(max_length=80, blank=True)
    reference = models.CharField("Nº de referencia", max_length=80, blank=True,
                                 help_text="Nº de transferencia, cheque, etc.")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ("-payment_date", "-created_at")
        indexes = [
            models.Index(fields=["purchase", "-payment_date"]),
            models.Index(fields=["payment_date"]),
        ]

    def __str__(self) -> str:
        return f"Pago {self.amount} {self.currency.code} @ {self.payment_date}"

    def amount_in_purchase_currency(self) -> Decimal:
        """Convierte el monto del pago a la moneda de la compra cuando difieren."""
        if self.currency_id == self.purchase.original_currency_id:
            return self.amount
        if self.exchange_rate_used:
            # exchange_rate.currency_from → currency_to con multiplicación.
            rate = self.exchange_rate_used
            if rate.rate_type.currency_from_id == self.currency_id and rate.rate_type.currency_to_id == self.purchase.original_currency_id:
                return (self.amount * rate.rate).quantize(Decimal("0.01"))
            if rate.rate_type.currency_from_id == self.purchase.original_currency_id and rate.rate_type.currency_to_id == self.currency_id:
                if rate.rate == 0:
                    return Decimal("0")
                return (self.amount / rate.rate).quantize(Decimal("0.01"))
        # Fallback: usar el servicio (busca default).
        from apps.pricing.services import CurrencyConversionService

        result = CurrencyConversionService.convert(
            self.amount, self.currency, self.purchase.original_currency,
            date=self.payment_date,
        )
        return result.amount.quantize(Decimal("0.01"))


def _payments_total_in_purchase_currency(purchase: Purchase) -> Decimal:
    """Suma de pagos de una compra, convertidos a su moneda original."""
    total = Decimal("0")
    for payment in purchase.payments.all():
        total += payment.amount_in_purchase_currency()
    return total


def update_purchase_payment_status(purchase: Purchase) -> None:
    """Recalcula `purchase.status` en base a los pagos cargados.

    - sin pagos    → mantiene el status que tenía (draft o to_pay).
    - 0 < pagos < total → paid_partial.
    - pagos ≥ total → paid.
    No toca cancelled.
    """
    if purchase.status == Purchase.Status.CANCELLED:
        return

    paid = _payments_total_in_purchase_currency(purchase)
    new_status = purchase.status

    if paid <= 0:
        # Si estaba paid_partial/paid pero borraron todos los pagos, vuelve a to_pay.
        if purchase.status in (Purchase.Status.PAID, Purchase.Status.PAID_PARTIAL):
            new_status = Purchase.Status.TO_PAY
    elif paid + Decimal("0.01") >= purchase.total_amount:
        new_status = Purchase.Status.PAID
    else:
        new_status = Purchase.Status.PAID_PARTIAL

    if new_status != purchase.status:
        Purchase.objects.filter(pk=purchase.pk).update(status=new_status)
