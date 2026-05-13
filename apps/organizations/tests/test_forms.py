"""Tests de validación del formulario de signup (sin tocar la DB)."""

from __future__ import annotations

from unittest.mock import patch

from apps.organizations.forms import OrganizationSignupForm


def _base_data(**overrides) -> dict:
    data = {
        "organization_name": "Constructora Ejemplo",
        "organization_slug": "ejemplo",
        "tax_id": "30-12345678-9",
        "first_name": "Mateo",
        "last_name": "Monsegur",
        "email": "mateo@ejemplo.com",
        "password": "ContraseñaLarga123!",
        "password_confirm": "ContraseñaLarga123!",
    }
    data.update(overrides)
    return data


def test_password_mismatch_is_rejected() -> None:
    form = OrganizationSignupForm(data=_base_data(password_confirm="otraCosa1234!"))
    with patch("apps.organizations.forms.Organization.objects.filter") as f_org, \
         patch("apps.organizations.forms.User.objects.filter") as f_user:
        f_org.return_value.exists.return_value = False
        f_user.return_value.exists.return_value = False
        assert not form.is_valid()
        assert "password_confirm" in form.errors


def test_reserved_slugs_are_rejected() -> None:
    form = OrganizationSignupForm(data=_base_data(organization_slug="admin"))
    with patch("apps.organizations.forms.Organization.objects.filter") as f_org, \
         patch("apps.organizations.forms.User.objects.filter") as f_user:
        f_org.return_value.exists.return_value = False
        f_user.return_value.exists.return_value = False
        assert not form.is_valid()
        assert "organization_slug" in form.errors
