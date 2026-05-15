"""Signals que crean TreasuryEntry automáticamente.

- PurchasePayment → expense / supplier_payment
- SocialChargesPayment → expense / social_charges_payment
- (TODO) PayrollPeriod.status=paid → expense / payroll_payment

Idempotente: si ya existe un TreasuryEntry vinculado al source, lo
actualiza en vez de duplicar.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.payroll.models import SocialChargesPayment
from apps.procurement.models import PurchasePayment

from .models import TreasuryEntry


@receiver(post_save, sender=PurchasePayment)
def create_entry_for_purchase_payment(sender, instance: PurchasePayment, **kwargs) -> None:
    purchase = instance.purchase
    TreasuryEntry.objects.update_or_create(
        source_purchase_payment=instance,
        defaults={
            "entry_type": TreasuryEntry.EntryType.EXPENSE,
            "category": TreasuryEntry.Category.SUPPLIER_PAYMENT,
            "date": instance.payment_date,
            "company": purchase.company,
            "bank_account": instance.bank_account if hasattr(instance, "bank_account") else None,
            "amount": instance.amount,
            "currency": instance.currency,
            "exchange_rate_used": instance.exchange_rate_used,
            "project": purchase.project,
            "description": (
                f"Pago compra {purchase.get_document_type_display()} "
                f"{purchase.document_number} · {purchase.supplier.name}"
            )[:300],
        },
    )


@receiver(post_delete, sender=PurchasePayment)
def delete_entry_for_purchase_payment(sender, instance: PurchasePayment, **kwargs) -> None:
    TreasuryEntry.objects.filter(source_purchase_payment=instance).delete()


@receiver(post_save, sender=SocialChargesPayment)
def create_entry_for_social_charges(sender, instance: SocialChargesPayment, **kwargs) -> None:
    TreasuryEntry.objects.update_or_create(
        source_social_charges_payment=instance,
        defaults={
            "entry_type": TreasuryEntry.EntryType.EXPENSE,
            "category": TreasuryEntry.Category.SOCIAL_CHARGES_PAYMENT,
            "date": instance.payment_date,
            "company": instance.company,
            "amount": instance.total_amount,
            "currency": instance.currency,
            "description": (
                f"Carga Social {instance.period_month:02d}/{instance.period_year} "
                f"· {instance.company.name}"
                f"{(' · ' + instance.reference) if instance.reference else ''}"
            )[:300],
        },
    )


@receiver(post_delete, sender=SocialChargesPayment)
def delete_entry_for_social_charges(sender, instance: SocialChargesPayment, **kwargs) -> None:
    TreasuryEntry.objects.filter(source_social_charges_payment=instance).delete()
