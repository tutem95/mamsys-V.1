from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    """Placeholder del dashboard dentro de un tenant.

    Si el tenant todavía no tiene ninguna Sociedad (Company), redirige al
    wizard de creación para completar el onboarding mínimo.
    """

    template_name = "core/dashboard.html"

    def get(self, request):
        from apps.companies.models import Company

        if not Company.objects.exists():
            return redirect("companies:create")

        context = {
            "companies": Company.objects.filter(active=True),
            "placeholder_cards": [
                "Obras", "Compras", "Quincenas",
                "Presupuestos", "Tesorería", "Reportes",
            ],
        }
        return render(request, self.template_name, context)
