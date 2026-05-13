"""URLs del schema PUBLIC.

Aquí va el sign-up de nuevas organizaciones y la landing comercial.
El admin de Django también vive acá (para el super-admin del SaaS).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.organizations.urls")),
]
