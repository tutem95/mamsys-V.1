"""Signals de payroll.

Cuando cambian Extraordinarios o Allocations de una entry, ésta se recalcula
para mantener extraordinary_subtotal y los montos prorrateados al día.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import PayrollAllocation, PayrollExtraordinary, SocialChargesPayment
from .services import SocialChargesProrateService


@receiver(post_save, sender=PayrollExtraordinary)
@receiver(post_delete, sender=PayrollExtraordinary)
def recompute_entry_on_extraordinary_change(sender, instance: PayrollExtraordinary, **kwargs) -> None:
    instance.payroll_entry.save()


@receiver(post_save, sender=SocialChargesPayment)
def prorate_on_payment_save(sender, instance: SocialChargesPayment, created: bool, **kwargs) -> None:
    """Dispara el prorrateo en cada save (alta o edición de monto)."""
    SocialChargesProrateService.prorate(instance)


@receiver(post_save, sender=PayrollAllocation)
def recompute_allocation_amounts(sender, instance: PayrollAllocation, created: bool, **kwargs) -> None:
    """Si se creó una allocation nueva, repartir gross/net del entry.

    Solo hace falta correr esto cuando created=True para evitar loop infinito
    con el save dentro de recalculate_allocations(). Las modificaciones de pct
    también se repartirán al re-guardar la entry (botón "Guardar liquidación").
    """
    if not created:
        return
    entry = instance.payroll_entry
    pct = (instance.pct or 0) / 100
    instance.jornal_amount = entry.gross * pct
    instance.net_amount = entry.net * pct
    instance.total_amount = instance.net_amount + (instance.social_charges_amount or 0)
    # update_fields evita disparar este mismo signal recursivamente.
    PayrollAllocation.objects.filter(pk=instance.pk).update(
        jornal_amount=instance.jornal_amount,
        net_amount=instance.net_amount,
        total_amount=instance.total_amount,
    )
