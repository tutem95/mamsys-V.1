"""Decoradores y mixin para gating de permisos en views.

Patrón:
- Function-based view: `@require_permission(P.VIEW_PURCHASES)`.
- Class-based view: mixin `PermissionRequiredMixin` con `required_permission`.

`user_has_permission` (en checks.py) ya respeta superuser y devuelve True
para super-admins de la plataforma.

`get_current_org` extrae el tenant de `request.tenant` (django-tenants).
En el schema `public` no aplica gating (devuelve None y dejamos pasar — la
landing/signup pública no tiene permisos).
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import redirect

from .checks import user_has_permission


def get_current_org(request: HttpRequest):
    """Devuelve el Organization del tenant actual, o None si estamos en public."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return None
    # En el schema público, tenant.schema_name == 'public'.
    if getattr(tenant, "schema_name", None) == "public":
        return None
    return tenant


def _deny(request: HttpRequest, code: str):
    msg = f"No tenés permiso para acceder a esta sección ({code})."
    messages.error(request, msg)
    return redirect("/")


def require_permission(code: str):
    """Decorator para function-based views.

    Si el user no está autenticado → redirect a login.
    Si no tiene `code` para la org actual → mensaje + redirect a home.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("account_login")
            org = get_current_org(request)
            if org is None:
                # public schema: las views que requieren permisos no deberían
                # estar montadas acá, pero dejamos pasar para no romper.
                return view_func(request, *args, **kwargs)
            if not user_has_permission(request.user, org, code):
                return _deny(request, code)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class PermissionRequiredMixin:
    """Mixin para CBVs. Definir `required_permission = "code"`.

    Si necesitás chequear múltiples permisos, overridear `has_required_permission`.
    """

    required_permission: str | None = None

    def has_required_permission(self) -> bool:
        if self.required_permission is None:
            return True
        org = get_current_org(self.request)
        if org is None:
            return True  # public schema, no gating
        return user_has_permission(self.request.user, org, self.required_permission)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not self.has_required_permission():
            return _deny(request, self.required_permission or "?")
        return super().dispatch(request, *args, **kwargs)
