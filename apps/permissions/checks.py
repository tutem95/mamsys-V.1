"""Helpers para verificar permisos en views/querysets."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.organizations.models import Organization


def user_has_permission(user: "User", organization: "Organization", code: str) -> bool:
    """¿El usuario tiene `code` dentro de la organización dada (vía su Membership)?"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    membership = (
        user.memberships.filter(organization=organization, is_active=True)
        .select_related("role")
        .first()
    )
    if membership is None:
        return False
    return membership.role.has_permission(code)
