"""URLs del schema PUBLIC.

Aquí va el sign-up de nuevas organizaciones y la landing comercial.
El admin de Django también vive acá (para el super-admin del SaaS).
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.organizations.urls")),
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
