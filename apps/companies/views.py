from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from .forms import CompanyForm
from .models import Company


@method_decorator(login_required, name="dispatch")
class CompanyCreateView(View):
    """Crea una Sociedad. Usado como wizard cuando el tenant no tiene ninguna."""

    template_name = "companies/form.html"

    def get(self, request):
        is_first = not Company.objects.exists()
        return render(request, self.template_name, {"form": CompanyForm(), "is_first": is_first})

    def post(self, request):
        form = CompanyForm(request.POST)
        is_first = not Company.objects.exists()
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "is_first": is_first})
        company = form.save(commit=False)
        company.created_by = request.user
        company.save()
        messages.success(request, f"Sociedad “{company.name}” creada.")
        return redirect("core:dashboard")
