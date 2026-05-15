"""Decorator + mixin de permisos."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.permissions.decorators import (
    PermissionRequiredMixin,
    get_current_org,
    require_permission,
)


def _make_request(*, authenticated=True, tenant=None):
    factory = RequestFactory()
    request = factory.get("/")
    user = MagicMock()
    user.is_authenticated = authenticated
    user.is_superuser = False
    request.user = user
    request.tenant = tenant
    # Hook para messages framework.
    request._messages = MagicMock()
    return request


def test_get_current_org_returns_none_in_public_schema() -> None:
    tenant = MagicMock()
    tenant.schema_name = "public"
    request = _make_request(tenant=tenant)
    assert get_current_org(request) is None


def test_get_current_org_returns_tenant_when_tenant_schema() -> None:
    tenant = MagicMock()
    tenant.schema_name = "acme"
    request = _make_request(tenant=tenant)
    assert get_current_org(request) is tenant


def test_require_permission_redirects_unauthenticated() -> None:
    @require_permission("view_purchases")
    def view(request):
        return HttpResponse("OK")

    request = _make_request(authenticated=False)
    response = view(request)
    assert response.status_code == 302
    assert response.url == "/accounts/login/"


def test_require_permission_lets_through_in_public_schema() -> None:
    @require_permission("view_purchases")
    def view(request):
        return HttpResponse("OK")

    tenant = MagicMock()
    tenant.schema_name = "public"
    request = _make_request(tenant=tenant)
    response = view(request)
    assert response.status_code == 200
    assert response.content == b"OK"


def test_require_permission_denies_when_user_has_no_perm(monkeypatch) -> None:
    # Forzamos a user_has_permission a devolver False.
    monkeypatch.setattr(
        "apps.permissions.decorators.user_has_permission",
        lambda u, o, c: False,
    )

    @require_permission("view_purchases")
    def view(request):
        return HttpResponse("OK")

    tenant = MagicMock()
    tenant.schema_name = "acme"
    request = _make_request(tenant=tenant)
    response = view(request)
    # Redirect a home, no OK.
    assert response.status_code == 302
    assert response.url == "/"


def test_require_permission_allows_when_user_has_perm(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.permissions.decorators.user_has_permission",
        lambda u, o, c: True,
    )

    @require_permission("view_purchases")
    def view(request):
        return HttpResponse("OK")

    tenant = MagicMock()
    tenant.schema_name = "acme"
    request = _make_request(tenant=tenant)
    response = view(request)
    assert response.status_code == 200


def test_permission_required_mixin_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.permissions.decorators.user_has_permission",
        lambda u, o, c: False,
    )

    class FakeView(PermissionRequiredMixin):
        required_permission = "edit_purchases"

        def dispatch(self, request, *args, **kwargs):
            return super().dispatch(request, *args, **kwargs)

    tenant = MagicMock()
    tenant.schema_name = "acme"
    request = _make_request(tenant=tenant)
    view = FakeView()
    response = view.dispatch(request)
    assert response.status_code == 302  # deny → redirect home


def test_template_tag_has_perm(monkeypatch) -> None:
    from apps.permissions.templatetags.permissions_tags import has_perm

    monkeypatch.setattr(
        "apps.permissions.templatetags.permissions_tags.user_has_permission",
        lambda u, o, c: True,
    )

    tenant = MagicMock()
    tenant.schema_name = "acme"
    request = _make_request(tenant=tenant)
    context = {"request": request}
    assert has_perm(context, "view_purchases") is True


def test_template_tag_returns_false_for_anonymous() -> None:
    from apps.permissions.templatetags.permissions_tags import has_perm

    request = _make_request(authenticated=False)
    context = {"request": request}
    assert has_perm(context, "view_purchases") is False
