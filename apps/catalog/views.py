"""Vistas CRUD para los catálogos.

Cada catálogo registra su configuración en CATALOGS y la factory
`_build_views()` arma list/create/update views consistentes.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView, UpdateView

from . import forms as catalog_forms
from . import models as catalog_models


# ---------------------------------------------------------------------------
# Configuración por catálogo
# ---------------------------------------------------------------------------
# Cada entrada describe un catálogo: el slug se usa en URLs y nombres de view,
# `columns` define lo que ve el usuario en la lista.

CATALOGS: dict[str, dict[str, Any]] = {
    "rubro": {
        "model": catalog_models.Rubro,
        "form": catalog_forms.RubroForm,
        "label_plural": "Rubros",
        "label_singular": "rubro",
        "columns": [("name", "Nombre"), ("code", "Código"), ("active", "Activo")],
    },
    "subrubro": {
        "model": catalog_models.Subrubro,
        "form": catalog_forms.SubrubroForm,
        "label_plural": "Subrubros",
        "label_singular": "subrubro",
        "columns": [("rubro", "Rubro"), ("name", "Nombre"), ("active", "Activo")],
        "select_related": ("rubro",),
    },
    "unit": {
        "model": catalog_models.Unit,
        "form": catalog_forms.UnitForm,
        "label_plural": "Unidades",
        "label_singular": "unidad",
        "columns": [("symbol", "Símbolo"), ("name", "Nombre"), ("category", "Categoría"), ("active", "Activa")],
    },
    "businesscomponent": {
        "model": catalog_models.BusinessComponent,
        "form": catalog_forms.BusinessComponentForm,
        "label_plural": "Componentes",
        "label_singular": "componente",
        "columns": [("name", "Nombre"), ("code", "Código"), ("active", "Activo")],
    },
    "projectstatus": {
        "model": catalog_models.ProjectStatus,
        "form": catalog_forms.ProjectStatusForm,
        "label_plural": "Estados de obra",
        "label_singular": "estado de obra",
        "columns": [("name", "Nombre"), ("active", "Activo")],
    },
    "employeestatus": {
        "model": catalog_models.EmployeeStatus,
        "form": catalog_forms.EmployeeStatusForm,
        "label_plural": "Estados de empleado",
        "label_singular": "estado de empleado",
        "columns": [("name", "Nombre"), ("active", "Activo")],
    },
    "position": {
        "model": catalog_models.Position,
        "form": catalog_forms.PositionForm,
        "label_plural": "Puestos",
        "label_singular": "puesto",
        "columns": [("name", "Nombre"), ("code", "Código"), ("active", "Activo")],
    },
    "bank": {
        "model": catalog_models.Bank,
        "form": catalog_forms.BankForm,
        "label_plural": "Bancos",
        "label_singular": "banco",
        "columns": [("name", "Nombre"), ("code", "Código"), ("active", "Activo")],
    },
    "extraordinaryconcept": {
        "model": catalog_models.ExtraordinaryConcept,
        "form": catalog_forms.ExtraordinaryConceptForm,
        "label_plural": "Conceptos extraordinarios",
        "label_singular": "concepto",
        "columns": [("name", "Nombre"), ("type", "Tipo"), ("active", "Activo")],
    },
    "trackingcategory": {
        "model": catalog_models.TrackingCategory,
        "form": catalog_forms.TrackingCategoryForm,
        "label_plural": "Categorías de seguimiento",
        "label_singular": "categoría",
        "columns": [("name", "Nombre"), ("color", "Color"), ("active", "Activa")],
    },
    "supplier": {
        "model": catalog_models.Supplier,
        "form": catalog_forms.SupplierForm,
        "label_plural": "Proveedores",
        "label_singular": "proveedor",
        "columns": [("code", "Código"), ("name", "Nombre"), ("category", "Categoría"), ("active", "Activo")],
        "prefetch_related": ("rubros",),
    },
    "material": {
        "model": catalog_models.Material,
        "form": catalog_forms.MaterialForm,
        "label_plural": "Materiales",
        "label_singular": "material",
        "columns": [("name", "Nombre"), ("rubro", "Rubro"), ("unit", "Unidad"), ("last_known_price", "Último $")],
        "select_related": ("rubro", "subrubro", "unit"),
    },
    "subcontract": {
        "model": catalog_models.Subcontract,
        "form": catalog_forms.SubcontractForm,
        "label_plural": "Subcontratos",
        "label_singular": "subcontrato",
        "columns": [("name", "Nombre"), ("unit", "Unidad"), ("typical_supplier", "Proveedor habitual"), ("last_known_price", "Último $")],
        "select_related": ("unit", "typical_supplier"),
    },
    "team": {
        "model": catalog_models.Team,
        "form": catalog_forms.TeamForm,
        "label_plural": "Equipos",
        "label_singular": "equipo",
        "columns": [("name", "Nombre"), ("leader", "Líder"), ("active", "Activo")],
        "select_related": ("leader",),
    },
    "bankaccount": {
        "model": catalog_models.BankAccount,
        "form": catalog_forms.BankAccountForm,
        "label_plural": "Cuentas bancarias",
        "label_singular": "cuenta bancaria",
        "columns": [("bank", "Banco"), ("company", "Sociedad"), ("account_number", "Nº"), ("currency", "Moneda"), ("active", "Activa")],
        "select_related": ("bank", "company", "currency"),
    },
}


# ---------------------------------------------------------------------------
# Bases
# ---------------------------------------------------------------------------

class _CatalogListView(ListView):
    template_name = "catalog/list.html"
    paginate_by = 50
    title: str = ""
    columns: list[tuple[str, str]] = []
    create_url: str = ""
    edit_url_name: str = ""
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[str, ...] = ()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.prefetch_related:
            qs = qs.prefetch_related(*self.prefetch_related)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["columns"] = self.columns
        ctx["create_url"] = self.create_url
        ctx["edit_url_name"] = self.edit_url_name
        return ctx


class _CatalogFormMixin:
    template_name = "catalog/form.html"
    title: str = ""
    success_url_name: str = ""

    def get_success_url(self):
        return reverse_lazy(self.success_url_name)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        return ctx


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _build_views(slug: str, cfg: dict[str, Any]) -> dict[str, type]:
    """Genera ListView, CreateView y UpdateView para un catálogo dado."""
    model = cfg["model"]
    form = cfg["form"]
    label_plural = cfg["label_plural"]
    label_singular = cfg["label_singular"]

    list_url = f"catalog:{slug}_list"
    create_url = f"catalog:{slug}_create"
    edit_url = f"catalog:{slug}_edit"
    base = model.__name__

    list_attrs = {
        "model": model,
        "title": label_plural,
        "columns": cfg["columns"],
        "create_url": create_url,
        "edit_url_name": edit_url,
        "select_related": cfg.get("select_related", ()),
        "prefetch_related": cfg.get("prefetch_related", ()),
    }
    list_view = type(f"{base}ListView", (_CatalogListView,), list_attrs)
    list_view.dispatch = method_decorator(login_required)(list_view.dispatch)

    create_attrs = {
        "model": model,
        "form_class": form,
        "title": f"Nuevo {label_singular}",
        "success_url_name": list_url,
    }
    create_view = type(f"{base}CreateView", (_CatalogFormMixin, CreateView), create_attrs)
    create_view.dispatch = method_decorator(login_required)(create_view.dispatch)

    update_attrs = {
        "model": model,
        "form_class": form,
        "title": f"Editar {label_singular}",
        "success_url_name": list_url,
    }
    update_view = type(f"{base}UpdateView", (_CatalogFormMixin, UpdateView), update_attrs)
    update_view.dispatch = method_decorator(login_required)(update_view.dispatch)

    return {"list": list_view, "create": create_view, "update": update_view}


VIEWS: dict[str, dict[str, type]] = {slug: _build_views(slug, cfg) for slug, cfg in CATALOGS.items()}


# ---------------------------------------------------------------------------
# Índice de catálogos
# ---------------------------------------------------------------------------

@login_required
def catalog_index(request):
    cards = [
        {
            "label": cfg["label_plural"],
            "count": cfg["model"].objects.count(),
            "url": f"catalog:{slug}_list",
        }
        for slug, cfg in CATALOGS.items()
    ]
    return render(request, "catalog/index.html", {"cards": cards})
