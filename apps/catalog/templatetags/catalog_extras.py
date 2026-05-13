from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="getattr")
def do_getattr(obj, attr):
    """Permite acceder a atributos dinámicos en templates: {{ obj|getattr:'name' }}.

    Para campos `choices` de Django, devuelve el display si existe.
    """
    if obj is None:
        return None
    value = getattr(obj, attr, None)
    display_method = getattr(obj, f"get_{attr}_display", None)
    if callable(display_method):
        try:
            return display_method()
        except Exception:
            return value
    return value
