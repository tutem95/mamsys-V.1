"""Configuración global de pytest."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _media_storage(settings, tmp_path):
    """Aislar media en cada test para evitar contaminación."""
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def tenant(db):
    """Crea un tenant de pruebas y se queda en su schema durante el test.

    Útil para apps que viven en TENANT_APPS (companies, core.AuditLog, etc.).
    El schema se crea automáticamente porque Organization.auto_create_schema=True.
    """
    from django_tenants.utils import schema_context, schema_exists

    from apps.organizations.models import Domain, Organization

    schema = "testtenant"
    if not schema_exists(schema):
        org = Organization.objects.create(
            name="Test Tenant",
            slug=schema,
            schema_name=schema,
        )
        Domain.objects.create(domain=f"{schema}.localhost", tenant=org, is_primary=True)
    else:
        org = Organization.objects.get(schema_name=schema)

    with schema_context(schema):
        yield org
