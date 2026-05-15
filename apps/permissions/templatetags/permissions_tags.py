"""Template tags para gating en templates.

Uso:
    {% load permissions_tags %}
    {% has_perm "view_purchases" as can_view %}
    {% if can_view %}<a href="/compras/">Compras</a>{% endif %}
"""

from __future__ import annotations

from django import template

from apps.permissions.checks import user_has_permission
from apps.permissions.decorators import get_current_org

register = template.Library()


@register.simple_tag(takes_context=True)
def has_perm(context, code: str) -> bool:
    """¿El user logueado tiene `code` en la org actual?

    En el schema public devuelve True (no aplica gating). Si no hay user
    autenticado, False.
    """
    request = context.get("request")
    if request is None or not request.user.is_authenticated:
        return False
    org = get_current_org(request)
    if org is None:
        return True
    return user_has_permission(request.user, org, code)
