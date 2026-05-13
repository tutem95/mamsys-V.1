from django.urls import path

from .views import CATALOGS, VIEWS, catalog_index

app_name = "catalog"

# URL slugs en español para que las URLs queden naturales (/catalogos/materiales/...).
SLUG_PATHS: dict[str, str] = {
    "rubro": "rubros",
    "subrubro": "subrubros",
    "unit": "unidades",
    "businesscomponent": "componentes",
    "projectstatus": "estados-obra",
    "employeestatus": "estados-empleado",
    "position": "puestos",
    "bank": "bancos",
    "extraordinaryconcept": "conceptos-extraordinarios",
    "trackingcategory": "categorias-seguimiento",
    "supplier": "proveedores",
    "material": "materiales",
    "subcontract": "subcontratos",
}


def _patterns_for(slug: str) -> list:
    path_slug = SLUG_PATHS.get(slug, slug)
    views = VIEWS[slug]
    return [
        path(f"{path_slug}/", views["list"].as_view(), name=f"{slug}_list"),
        path(f"{path_slug}/nuevo/", views["create"].as_view(), name=f"{slug}_create"),
        path(f"{path_slug}/<int:pk>/editar/", views["update"].as_view(), name=f"{slug}_edit"),
    ]


urlpatterns = [path("", catalog_index, name="index")]
for _slug in CATALOGS:
    urlpatterns.extend(_patterns_for(_slug))
