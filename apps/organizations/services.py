"""Servicios de organizaciones."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.permissions.models import Role

from .models import Domain, Membership, Organization


@dataclass
class SignupResult:
    organization: Organization
    user: User
    domain: Domain
    membership: Membership


@transaction.atomic
def signup_organization(
    *,
    organization_name: str,
    organization_slug: str,
    tax_id: str,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> SignupResult:
    """Crea una organización nueva con su tenant, dominio y primer admin.

    Pasos:
    1. Crear el User (vive en `public`).
    2. Crear la Organization → django-tenants crea el schema automáticamente.
    3. El signal `provision_default_roles` carga los 5 roles base.
    4. Crear Domain `<slug>.<TENANT_BASE_DOMAIN>` apuntando a la org.
    5. Crear Membership del primer user con rol Admin.
    """
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email_verified=True,
    )

    organization = Organization.objects.create(
        name=organization_name,
        slug=organization_slug,
        tax_id=tax_id,
        schema_name=organization_slug,
    )

    base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "localhost")
    domain = Domain.objects.create(
        domain=f"{organization_slug}.{base_domain}",
        tenant=organization,
        is_primary=True,
    )

    admin_role = Role.objects.get(organization=organization, name="Admin")
    membership = Membership.objects.create(
        user=user,
        organization=organization,
        role=admin_role,
        is_active=True,
    )

    return SignupResult(
        organization=organization,
        user=user,
        domain=domain,
        membership=membership,
    )
