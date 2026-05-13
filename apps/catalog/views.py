"""Vistas CRUD para los catálogos.

Patrón: cada catálogo declara una subclase de `CatalogListView`,
`CatalogCreateView` y `CatalogUpdateView` con sus atributos. Las templates
genéricas se reutilizan.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView, UpdateView

from .forms import BusinessComponentForm, RubroForm, SubrubroForm, UnitForm
from .models import BusinessComponent, Rubro, Subrubro, Unit


@login_required
def catalog_index(request):
    """Página de inicio de catálogos: tarjetas con conteo y links a cada uno."""
    cards = [
        {"label": "Rubros", "count": Rubro.objects.count(), "url": "catalog:rubro_list"},
        {"label": "Subrubros", "count": Subrubro.objects.count(), "url": "catalog:subrubro_list"},
        {"label": "Unidades", "count": Unit.objects.count(), "url": "catalog:unit_list"},
        {"label": "Componentes", "count": BusinessComponent.objects.count(), "url": "catalog:businesscomponent_list"},
    ]
    return render(request, "catalog/index.html", {"cards": cards})


# ---------------------------------------------------------------------------
# Vistas genéricas
# ---------------------------------------------------------------------------

class _CatalogListView(ListView):
    template_name = "catalog/list.html"
    paginate_by = 50
    title: str = ""
    columns: list[tuple[str, str]] = []
    create_url: str = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["columns"] = self.columns
        ctx["create_url"] = self.create_url
        ctx["edit_url_name"] = getattr(self, "edit_url_name", "")
        return ctx


class _CatalogFormView:
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
# Rubro
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class RubroListView(_CatalogListView):
    model = Rubro
    title = "Rubros"
    columns = [("name", "Nombre"), ("code", "Código"), ("active", "Activo")]
    create_url = "catalog:rubro_create"
    edit_url_name = "catalog:rubro_edit"


@method_decorator(login_required, name="dispatch")
class RubroCreateView(_CatalogFormView, CreateView):
    model = Rubro
    form_class = RubroForm
    title = "Nuevo rubro"
    success_url_name = "catalog:rubro_list"


@method_decorator(login_required, name="dispatch")
class RubroUpdateView(_CatalogFormView, UpdateView):
    model = Rubro
    form_class = RubroForm
    title = "Editar rubro"
    success_url_name = "catalog:rubro_list"


# ---------------------------------------------------------------------------
# Subrubro
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class SubrubroListView(_CatalogListView):
    model = Subrubro
    title = "Subrubros"
    columns = [("rubro", "Rubro"), ("name", "Nombre"), ("active", "Activo")]
    create_url = "catalog:subrubro_create"
    edit_url_name = "catalog:subrubro_edit"

    def get_queryset(self):
        return super().get_queryset().select_related("rubro")


@method_decorator(login_required, name="dispatch")
class SubrubroCreateView(_CatalogFormView, CreateView):
    model = Subrubro
    form_class = SubrubroForm
    title = "Nuevo subrubro"
    success_url_name = "catalog:subrubro_list"


@method_decorator(login_required, name="dispatch")
class SubrubroUpdateView(_CatalogFormView, UpdateView):
    model = Subrubro
    form_class = SubrubroForm
    title = "Editar subrubro"
    success_url_name = "catalog:subrubro_list"


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class UnitListView(_CatalogListView):
    model = Unit
    title = "Unidades"
    columns = [("symbol", "Símbolo"), ("name", "Nombre"), ("category", "Categoría"), ("active", "Activa")]
    create_url = "catalog:unit_create"
    edit_url_name = "catalog:unit_edit"


@method_decorator(login_required, name="dispatch")
class UnitCreateView(_CatalogFormView, CreateView):
    model = Unit
    form_class = UnitForm
    title = "Nueva unidad"
    success_url_name = "catalog:unit_list"


@method_decorator(login_required, name="dispatch")
class UnitUpdateView(_CatalogFormView, UpdateView):
    model = Unit
    form_class = UnitForm
    title = "Editar unidad"
    success_url_name = "catalog:unit_list"


# ---------------------------------------------------------------------------
# BusinessComponent
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class BusinessComponentListView(_CatalogListView):
    model = BusinessComponent
    title = "Componentes"
    columns = [("name", "Nombre"), ("code", "Código"), ("active", "Activo")]
    create_url = "catalog:businesscomponent_create"
    edit_url_name = "catalog:businesscomponent_edit"


@method_decorator(login_required, name="dispatch")
class BusinessComponentCreateView(_CatalogFormView, CreateView):
    model = BusinessComponent
    form_class = BusinessComponentForm
    title = "Nuevo componente"
    success_url_name = "catalog:businesscomponent_list"


@method_decorator(login_required, name="dispatch")
class BusinessComponentUpdateView(_CatalogFormView, UpdateView):
    model = BusinessComponent
    form_class = BusinessComponentForm
    title = "Editar componente"
    success_url_name = "catalog:businesscomponent_list"
