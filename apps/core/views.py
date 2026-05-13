from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    """Placeholder del dashboard dentro de un tenant."""

    template_name = "core/dashboard.html"

    def get(self, request):
        context = {
            "placeholder_cards": [
                "Obras", "Compras", "Quincenas",
                "Presupuestos", "Tesorería", "Reportes",
            ],
        }
        return render(request, self.template_name, context)
