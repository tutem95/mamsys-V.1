from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_index, name="index"),

    path("rubros/", views.RubroListView.as_view(), name="rubro_list"),
    path("rubros/nuevo/", views.RubroCreateView.as_view(), name="rubro_create"),
    path("rubros/<int:pk>/editar/", views.RubroUpdateView.as_view(), name="rubro_edit"),

    path("subrubros/", views.SubrubroListView.as_view(), name="subrubro_list"),
    path("subrubros/nuevo/", views.SubrubroCreateView.as_view(), name="subrubro_create"),
    path("subrubros/<int:pk>/editar/", views.SubrubroUpdateView.as_view(), name="subrubro_edit"),

    path("unidades/", views.UnitListView.as_view(), name="unit_list"),
    path("unidades/nueva/", views.UnitCreateView.as_view(), name="unit_create"),
    path("unidades/<int:pk>/editar/", views.UnitUpdateView.as_view(), name="unit_edit"),

    path("componentes/", views.BusinessComponentListView.as_view(), name="businesscomponent_list"),
    path("componentes/nuevo/", views.BusinessComponentCreateView.as_view(), name="businesscomponent_create"),
    path("componentes/<int:pk>/editar/", views.BusinessComponentUpdateView.as_view(), name="businesscomponent_edit"),
]
