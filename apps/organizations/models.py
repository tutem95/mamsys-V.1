"""Modelos de tenancy y multi-organización.

- Organization es el tenant de django-tenants (schema-per-org en Postgres).
- Domain mapea hosts/subdominios a Organizations.
- Membership relaciona User ↔ Organization con un Role (de permissions).
- Invitation deja invitar a un email a una org antes de que el usuario exista.

Estos modelos viven en el schema `public` (SHARED_APPS).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.timezone import now as tz_now
from django_tenants.models import DomainMixin, TenantMixin


class Organization(TenantMixin):
    """Cliente del SaaS. Cada uno tiene su propio schema en Postgres."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    legal_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField("CUIT", max_length=20, blank=True)

    country = models.CharField(max_length=2, default="AR")
    timezone = models.CharField(max_length=64, default="America/Argentina/Buenos_Aires")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=tz_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    # django-tenants: crear el schema automáticamente cuando se inserta el registro.
    auto_create_schema = True
    auto_drop_schema = False  # nunca borrar schemas en silencio

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    """Mapeo subdominio → Organization (parte de django-tenants)."""

    pass


class Membership(models.Model):
    """Vínculo User ↔ Organization con un Role.

    Un mismo usuario puede pertenecer a varias orgs (ej.: consultor).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.ForeignKey(
        "permissions.Role",
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "organization"),)
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization}"


class Invitation(models.Model):
    """Invitación pendiente para que alguien se sume a una org."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.ForeignKey(
        "permissions.Role",
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "email"]),
            models.Index(fields=["token"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization}"
