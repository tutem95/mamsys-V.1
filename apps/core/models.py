"""Modelos abstractos y mixins transversales.

TODO(tenancy): la spec menciona un OrganizationOwnedModel con FK directa a Organization.
Con django-tenants los FK cross-schema son problemáticos (tenant -> public). Por ahora
queda fuera; se reintroducirá si surge un caso real (probablemente almacenando el
organization_id como UUID/int plano sin FK de DB).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class CatalogItem(TimestampedModel):
    """Base para catálogos editables por el usuario.

    Subclases deben definir Meta(ordering=...) o heredar el default.
    """

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name


class AuditLog(models.Model):
    """Registro automático de cambios sensibles.

    Lo escriben signals desde modelos críticos (Purchase, PayrollEntry, Budget, etc.).
    Vive en el schema del tenant: cada org tiene su propia bitácora.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        APPROVE = "approve", "Approve"
        CLOSE = "close", "Close"
        REOPEN = "reopen", "Reopen"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey("content_type", "object_id")
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["-timestamp"]),
        ]
        ordering = ("-timestamp",)
