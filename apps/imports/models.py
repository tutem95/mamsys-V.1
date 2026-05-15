"""ImportLog: registro de cada importación con su resumen y errores.

No persistimos los archivos (se procesan en memoria) pero sí el log para
auditoría: quién importó qué, cuántas filas, cuántas con error.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class ImportLog(TimestampedModel):
    class Status(models.TextChoices):
        DRY_RUN = "dry_run", "Vista previa"
        COMMITTED = "committed", "Confirmado"
        FAILED = "failed", "Fallido"

    importer_slug = models.CharField(max_length=60)
    importer_label = models.CharField(max_length=120)
    filename = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)

    rows_total = models.PositiveIntegerField(default=0)
    rows_ok = models.PositiveIntegerField(default=0)
    rows_error = models.PositiveIntegerField(default=0)
    rows_created = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)

    errors = models.JSONField(default=list, blank=True,
                              help_text="Lista de errores por fila: [{row, message}, ...]")
    summary = models.TextField(blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Importación"
        verbose_name_plural = "Importaciones"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["importer_slug", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.importer_label} · {self.created_at:%d/%m/%Y %H:%M}"
