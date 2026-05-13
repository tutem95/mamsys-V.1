"""Tests puros (no requieren DB) del catálogo de permisos."""

from __future__ import annotations

from apps.permissions import constants as P
from apps.permissions.services import DEFAULT_ROLES


def test_no_duplicate_permission_codes() -> None:
    assert len(P.ALL_PERMISSIONS) == len(set(P.ALL_PERMISSIONS))


def test_permission_codes_are_snake_case() -> None:
    for code in P.ALL_PERMISSIONS:
        assert code == code.lower(), f"{code} no es lowercase"
        assert " " not in code, f"{code} tiene espacios"
        assert "-" not in code, f"{code} usa guion en vez de underscore"


def test_default_roles_use_valid_permissions() -> None:
    valid = set(P.ALL_PERMISSIONS)
    for role_name, cfg in DEFAULT_ROLES.items():
        for code in cfg["permissions"]:
            assert code in valid, f"Rol {role_name} usa permiso desconocido: {code}"


def test_admin_role_has_every_permission() -> None:
    admin = DEFAULT_ROLES["Admin"]
    assert set(admin["permissions"]) == set(P.ALL_PERMISSIONS)
