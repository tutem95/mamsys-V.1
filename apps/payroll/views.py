from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from .forms import (
    EmergencyContactFormSet,
    EmployeeBankingForm,
    EmployeeForm,
    EmployeePersonalDataForm,
)
from .models import Employee, EmployeeBanking, EmployeePersonalData


@method_decorator(login_required, name="dispatch")
class EmployeeListView(ListView):
    model = Employee
    template_name = "payroll/employee_list.html"
    paginate_by = 50
    context_object_name = "employees"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("company", "status", "position", "personal_data")
            .prefetch_related("teams")
        )
        f = self.request.GET
        if f.get("estado"):
            qs = qs.filter(status_id=f["estado"])
        if f.get("sociedad"):
            qs = qs.filter(company_id=f["sociedad"])
        if f.get("puesto"):
            qs = qs.filter(position_id=f["puesto"])
        if f.get("equipo"):
            qs = qs.filter(teams__id=f["equipo"]).distinct()
        if f.get("q"):
            q = f["q"]
            qs = qs.filter(
                Q(personal_data__first_name__icontains=q)
                | Q(personal_data__last_name__icontains=q)
                | Q(internal_id__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        from apps.catalog.models import EmployeeStatus, Position, Team
        from apps.companies.models import Company

        ctx = super().get_context_data(**kwargs)
        f = self.request.GET
        ctx["current_q"] = f.get("q", "")
        ctx["current_estado"] = f.get("estado", "")
        ctx["current_sociedad"] = f.get("sociedad", "")
        ctx["current_puesto"] = f.get("puesto", "")
        ctx["current_equipo"] = f.get("equipo", "")
        ctx["statuses"] = EmployeeStatus.objects.filter(active=True).order_by("order", "name")
        ctx["companies"] = Company.objects.filter(active=True).order_by("name")
        ctx["positions"] = Position.objects.filter(active=True).order_by("name")
        ctx["teams"] = Team.objects.filter(active=True).order_by("name")
        return ctx


@method_decorator(login_required, name="dispatch")
class EmployeeDetailView(DetailView):
    model = Employee
    template_name = "payroll/employee_detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related(
                "company", "status", "position", "primary_rubro", "boss",
                "personal_data", "banking", "banking__bank",
                "last_known_currency",
            )
            .prefetch_related("teams", "emergency_contacts")
        )


@login_required
def employee_create(request):
    return _employee_form(request, instance=None)


@login_required
def employee_edit(request, pk: int):
    employee = get_object_or_404(Employee, pk=pk)
    return _employee_form(request, instance=employee)


def _employee_form(request, instance: Employee | None):
    # Recuperar relacionados si existen.
    personal_instance = getattr(instance, "personal_data", None) if instance else None
    banking_instance = getattr(instance, "banking", None) if instance else None

    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=instance)
        personal_form = EmployeePersonalDataForm(request.POST, instance=personal_instance)
        banking_form = EmployeeBankingForm(request.POST, instance=banking_instance)
        emergency_set = EmergencyContactFormSet(request.POST, instance=instance or Employee())

        if form.is_valid() and personal_form.is_valid() and banking_form.is_valid() and emergency_set.is_valid():
            with transaction.atomic():
                emp = form.save(commit=False)
                if instance is None:
                    emp.created_by = request.user
                emp.updated_by = request.user
                emp.save()
                form.save_m2m()

                personal = personal_form.save(commit=False)
                personal.employee = emp
                personal.save()

                banking = banking_form.save(commit=False)
                banking.employee = emp
                banking.save()

                emergency_set.instance = emp
                emergency_set.save()

            messages.success(request, "Empleado guardado.")
            return redirect("payroll:detail", pk=emp.pk)
    else:
        form = EmployeeForm(instance=instance)
        personal_form = EmployeePersonalDataForm(instance=personal_instance)
        banking_form = EmployeeBankingForm(instance=banking_instance)
        emergency_set = EmergencyContactFormSet(instance=instance or Employee())

    return render(request, "payroll/employee_form.html", {
        "form": form,
        "personal_form": personal_form,
        "banking_form": banking_form,
        "emergency_set": emergency_set,
        "employee": instance,
    })
