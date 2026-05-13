"""Tests de integración del flujo de signup.

Requieren Postgres porque django-tenants crea schemas reales. Se marcan con
`pytest.mark.django_db` y se omiten si no hay DB configurada.
"""

from __future__ import annotations

import pytest

from apps.organizations.models import Domain, Membership, Organization
from apps.organizations.services import signup_organization
from apps.permissions.models import Role


@pytest.mark.django_db
def test_signup_creates_org_user_domain_and_admin_membership() -> None:
    result = signup_organization(
        organization_name="Constructora Test",
        organization_slug="test-co",
        tax_id="30-99999999-0",
        first_name="Test",
        last_name="User",
        email="admin@test-co.com",
        password="ContraseñaLarga123!",
    )

    assert Organization.objects.filter(slug="test-co").exists()
    assert Domain.objects.filter(tenant=result.organization).exists()
    assert result.membership.role.name == "Admin"
    assert Membership.objects.filter(user=result.user).count() == 1


@pytest.mark.django_db
def test_signup_provisions_five_default_roles() -> None:
    result = signup_organization(
        organization_name="Constructora Roles",
        organization_slug="roles-co",
        tax_id="",
        first_name="Test",
        last_name="User",
        email="admin@roles-co.com",
        password="ContraseñaLarga123!",
    )
    role_names = set(Role.objects.filter(organization=result.organization).values_list("name", flat=True))
    assert role_names == {"Admin", "Área Técnica / Gestión", "Tesorería", "RRHH / Nómina", "Solo Lectura"}
