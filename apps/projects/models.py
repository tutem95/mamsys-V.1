"""Modelo Project (Obra).

Vive en TENANT. La FK a `accounts.User` (SHARED) funciona con django-tenants
porque el search_path incluye `public`; PostgreSQL resuelve el FK a la tabla
de usuarios en el schema público.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class Project(TimestampedModel):
    """Obra. Pertenece a una Sociedad (Company) y tiene un Estado."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, blank=True)

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        related_name="projects",
    )
    status = models.ForeignKey(
        "catalog.ProjectStatus",
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )

    address = models.CharField(max_length=300, blank=True)

    start_date = models.DateField(null=True, blank=True)
    estimated_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)

    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_projects",
    )

    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Obra"
        verbose_name_plural = "Obras"
        ordering = ("-start_date", "name")
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="project_unique_name_per_company"),
            models.UniqueConstraint(
                fields=["code"], condition=~models.Q(code=""), name="project_unique_code",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_archived"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.name
