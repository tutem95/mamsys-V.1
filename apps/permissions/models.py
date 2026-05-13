"""Roles y permisos por objeto.

`Role` es por-organización: cada org puede tener su propio set de roles configurables.
Vive en el schema public junto con Membership.

`ObjectAccess` da permisos finos sobre objetos puntuales (una obra, una sociedad).
Como apunta a objetos que viven en schemas de tenant, este modelo usa GenericForeignKey
con ContentType + object_id, sin FK directa (django-tenants no soporta FK cross-schema).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Role(models.Model):
    """Rol configurable dentro de una organización."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)

    # Lista de strings tomados de apps.permissions.constants.
    permissions = models.JSONField(default=list, blank=True)

    is_system = models.BooleanField(
        default=False,
        help_text="True para los roles base creados al provisionar la org. Pueden duplicarse pero no eliminarse.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("organization", "name"),)
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ("organization", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.organization})"

    def has_permission(self, code: str) -> bool:
        return code in (self.permissions or [])


class ObjectAccess(models.Model):
    """Acceso fino: dale a un usuario permiso sobre una obra o sociedad puntual.

    Como el objeto puede vivir en el schema del tenant, no hay FK directa.
    El consumidor (helpers/queries) resuelve el target vía ContentType + object_id
    dentro del schema corriente.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="object_access",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="object_access",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey("content_type", "object_id")

    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "organization", "content_type", "object_id"),)
        indexes = [
            models.Index(fields=["user", "organization"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "Acceso por objeto"
        verbose_name_plural = "Accesos por objeto"
