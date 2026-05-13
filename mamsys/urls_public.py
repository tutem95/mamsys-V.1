"""URLs del schema PUBLIC (landing del SaaS, signup de organización, etc.).

Para Fase 1 dejamos solo accounts + admin. La landing comercial se arma después.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
]
