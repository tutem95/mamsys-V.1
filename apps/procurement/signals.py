"""Signals de procurement.

Cuando un PurchaseItem se guarda en una compra confirmada (status != draft):
- Upsert de un Price para el item (referenciable por future PriceLookupService).
- Actualizar `last_known_price` del Material/Subcontract.

Cuando se guarda/borra un PurchasePayment:
- Recalcular el status de la compra (to_pay → paid_partial → paid).
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    Purchase,
    PurchaseItem,
    PurchasePayment,
    update_purchase_payment_status,
)


@receiver(post_save, sender=PurchaseItem)
def sync_price_from_item(sender, instance: PurchaseItem, created: bool, **kwargs) -> None:
    """Upsert un pricing.Price cuando un ítem se carga en compra confirmada."""
    purchase = instance.purchase
    if purchase.status == Purchase.Status.DRAFT:
        return

    target = instance.material or instance.subcontract
    if target is None:
        return

    # Import diferido para evitar dependencias circulares en migraciones.
    from apps.pricing.models import Price

    ct = ContentType.objects.get_for_model(target)
    Price.objects.update_or_create(
        source_purchase_item_id=instance.pk,
        defaults={
            "content_type": ct,
            "object_id": target.pk,
            "amount": instance.unit_price,
            "currency": purchase.original_currency,
            "effective_date": purchase.invoice_date,
            "source": Price.Source.PURCHASE,
            "supplier": purchase.supplier,
            "is_reference": True,
            "notes": f"De compra #{purchase.pk} {purchase.document_number}".strip(),
        },
    )

    # Actualizar cache last_known_price si el modelo lo tiene.
    if hasattr(target, "last_known_price"):
        type(target).objects.filter(pk=target.pk).update(last_known_price=instance.unit_price)


@receiver(post_save, sender=Purchase)
def propagate_status_to_items_pricing(sender, instance: Purchase, created: bool, **kwargs) -> None:
    """Si una compra pasó de draft → confirmada, alimentar Prices para sus items existentes."""
    if instance.status == Purchase.Status.DRAFT:
        return
    # Disparar el handler de ítem para cada uno. update_or_create es idempotente.
    for item in instance.items.all().iterator():
        sync_price_from_item(PurchaseItem, item, created=False)


@receiver(post_save, sender=PurchasePayment)
def recompute_status_on_payment_save(sender, instance: PurchasePayment, **kwargs) -> None:
    update_purchase_payment_status(instance.purchase)


@receiver(post_delete, sender=PurchasePayment)
def recompute_status_on_payment_delete(sender, instance: PurchasePayment, **kwargs) -> None:
    update_purchase_payment_status(instance.purchase)
