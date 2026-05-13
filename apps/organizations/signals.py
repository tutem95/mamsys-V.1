"""Signals para auto-provisionamiento al crear una Organization.

Cuando se crea una Organization:
- django-tenants crea el schema (vía auto_create_schema=True en el modelo).
- A continuación creamos los roles base de la organización.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Organization


@receiver(post_save, sender=Organization)
def provision_default_roles(sender, instance: Organization, created: bool, **kwargs) -> None:
    if not created:
        return
    # Import diferido para evitar circularidad en migraciones.
    from apps.permissions.services import create_default_roles

    create_default_roles(instance)
