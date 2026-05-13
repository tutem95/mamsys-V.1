"""URLs del schema TENANT (acceso desde un subdominio de organización)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # Apps de negocio se suman aquí a medida que avanzan las fases.
]
