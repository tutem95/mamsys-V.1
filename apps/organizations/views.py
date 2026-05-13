from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views import View

from .forms import OrganizationSignupForm
from .services import signup_organization


class OrganizationSignupView(View):
    """Vista pública para crear una nueva organización + primer admin.

    Solo se sirve desde el schema PUBLIC (urls_public.py).
    """

    template_name = "organizations/signup.html"

    def get(self, request):
        return render(request, self.template_name, {"form": OrganizationSignupForm()})

    def post(self, request):
        form = OrganizationSignupForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        result = signup_organization(
            organization_name=form.cleaned_data["organization_name"],
            organization_slug=form.cleaned_data["organization_slug"],
            tax_id=form.cleaned_data.get("tax_id", ""),
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )

        login(request, result.user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "¡Listo! Tu organización se creó correctamente.")

        # Redirigir al subdominio de la org recién creada.
        base = getattr(settings, "TENANT_BASE_DOMAIN", "localhost")
        scheme = "https" if request.is_secure() else "http"
        return redirect(f"{scheme}://{result.domain.domain}/")


class PublicLandingView(View):
    """Landing del schema público.

    Si el visitante está autenticado, mostramos sus organizaciones para que
    elija a cuál entrar. Si no, ofrecemos sign-up.
    """

    template_name = "organizations/landing.html"

    def get(self, request):
        memberships = []
        if request.user.is_authenticated:
            base = getattr(settings, "TENANT_BASE_DOMAIN", "localhost")
            host_port = request.get_host().split(":")
            port = f":{host_port[1]}" if len(host_port) > 1 else ""
            scheme = "https" if request.is_secure() else "http"
            qs = (
                request.user.memberships.filter(is_active=True)
                .select_related("organization", "role")
                .order_by("organization__name")
            )
            for m in qs:
                memberships.append({
                    "name": m.organization.name,
                    "role": m.role.name,
                    "url": f"{scheme}://{m.organization.slug}.{base}{port}/",
                })
        return render(request, self.template_name, {"memberships": memberships})
