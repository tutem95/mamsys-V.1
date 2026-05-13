"""URLs del schema TENANT (acceso desde un subdominio de organización)."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("sociedades/", include("apps.companies.urls")),
    path("catalogos/", include("apps.catalog.urls")),
    path("obras/", include("apps.projects.urls")),
    path("", include("apps.core.urls")),
    # Apps de negocio se suman aquí a medida que avanzan las fases.
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
