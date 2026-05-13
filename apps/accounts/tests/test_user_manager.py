from __future__ import annotations

import pytest

from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_normalizes_email_and_hashes_password() -> None:
    user = User.objects.create_user(email="Foo@Example.COM", password="ContraseñaLarga123!")
    assert user.email == "Foo@example.com"
    assert user.check_password("ContraseñaLarga123!")
    assert user.is_active and not user.is_staff and not user.is_superuser


@pytest.mark.django_db
def test_create_superuser_requires_flags() -> None:
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="bad@example.com",
            password="ContraseñaLarga123!",
            is_staff=False,
        )


@pytest.mark.django_db
def test_email_must_be_unique() -> None:
    User.objects.create_user(email="x@example.com", password="ContraseñaLarga123!")
    with pytest.raises(Exception):
        User.objects.create_user(email="x@example.com", password="ContraseñaLarga123!")
