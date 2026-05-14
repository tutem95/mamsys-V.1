from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from .forms import (
    EmergencyContactFormSet,
    EmployeeBankingForm,
    EmployeeForm,
    EmployeePersonalDataForm,
    PayrollAllocationFormSet,
    PayrollEntryForm,
    PayrollExtraordinaryFormSet,
    PayrollPeriodForm,
    PositionPlusFormSet,
    SocialChargesPaymentForm,
)
from .models import (
    Employee,
    EmployeeBanking,
    EmployeePersonalData,
    PayrollAllocation,
    PayrollEntry,
    PayrollPeriod,
    SocialChargesPayment,
    pre_generate_entries_for_period,
)
from .services import SocialChargesProrateService


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


# ---------------------------------------------------------------------------
# Quincenas (Turno B)
# ---------------------------------------------------------------------------


@method_decorator(login_required, name="dispatch")
class PayrollPeriodListView(ListView):
    model = PayrollPeriod
    template_name = "payroll/period_list.html"
    paginate_by = 50
    context_object_name = "periods"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("company")
            .annotate(entries_count=models.Count("entries"))
        )


@login_required
def period_create(request):
    """Crea una quincena nueva y pre-genera entradas para empleados activos."""
    if request.method == "POST":
        form = PayrollPeriodForm(request.POST)
        plus_set = PositionPlusFormSet(request.POST, instance=PayrollPeriod())
        if form.is_valid() and plus_set.is_valid():
            with transaction.atomic():
                period = form.save(commit=False)
                period.created_by = request.user
                period.updated_by = request.user
                period.save()
                plus_set.instance = period
                plus_set.save()
                # Generar las entradas para cada empleado activo.
                created = pre_generate_entries_for_period(period)
            messages.success(
                request,
                f"Quincena creada con {len(created)} entrada{'s' if len(created) != 1 else ''} pre-generadas.",
            )
            return redirect("payroll:period_detail", pk=period.pk)
    else:
        form = PayrollPeriodForm()
        plus_set = PositionPlusFormSet(instance=PayrollPeriod())

    return render(request, "payroll/period_form.html", {
        "form": form, "plus_set": plus_set, "period": None,
    })


@login_required
def period_edit(request, pk: int):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    if request.method == "POST":
        form = PayrollPeriodForm(request.POST, instance=period)
        plus_set = PositionPlusFormSet(request.POST, instance=period)
        if form.is_valid() and plus_set.is_valid():
            with transaction.atomic():
                p = form.save(commit=False)
                p.updated_by = request.user
                p.save()
                plus_set.save()
                # Si cambiaron los pluses o configuración, recalcular entradas.
                for entry in period.entries.all():
                    entry.save()  # dispara recalculate()
            messages.success(request, "Quincena actualizada y entradas recalculadas.")
            return redirect("payroll:period_detail", pk=period.pk)
    else:
        form = PayrollPeriodForm(instance=period)
        plus_set = PositionPlusFormSet(instance=period)

    return render(request, "payroll/period_form.html", {
        "form": form, "plus_set": plus_set, "period": period,
    })


@login_required
def period_detail(request, pk: int):
    period = get_object_or_404(
        PayrollPeriod.objects.select_related("company").prefetch_related("position_pluses__position"),
        pk=pk,
    )
    entries = (
        period.entries
        .select_related("employee", "employee__personal_data", "employee__position", "currency")
        .order_by("employee__personal_data__last_name", "employee__personal_data__first_name", "employee_id")
    )

    # Totales rápidos
    totals = entries.aggregate(
        gross=models.Sum("gross"),
        net=models.Sum("net"),
        bank=models.Sum("bank_amount"),
        cash=models.Sum("cash_amount"),
    )

    return render(request, "payroll/period_detail.html", {
        "period": period,
        "entries": entries,
        "totals": totals,
    })


@login_required
def period_regenerate_entries(request, pk: int):
    """Re-genera entradas faltantes (empleados nuevos desde que se creó la quincena)."""
    period = get_object_or_404(PayrollPeriod, pk=pk)
    if request.method == "POST":
        created = pre_generate_entries_for_period(period)
        if created:
            messages.success(request, f"{len(created)} entrada{'s' if len(created) != 1 else ''} agregadas.")
        else:
            messages.info(request, "No había empleados nuevos para sumar.")
    return redirect("payroll:period_detail", pk=period.pk)


@login_required
def entry_edit(request, pk: int):
    entry = get_object_or_404(
        PayrollEntry.objects.select_related("employee__personal_data", "payroll_period"),
        pk=pk,
    )
    if request.method == "POST":
        form = PayrollEntryForm(request.POST, instance=entry)
        extras_set = PayrollExtraordinaryFormSet(request.POST, instance=entry, prefix="extras")
        alloc_set = PayrollAllocationFormSet(request.POST, instance=entry, prefix="allocs")
        if form.is_valid() and extras_set.is_valid() and alloc_set.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                # Extraordinarios primero: sus signals recalculan la entry.
                extras_set.save()
                # Allocations: signals propagan jornal/net_amount.
                alloc_set.save()
                # Final recalc para asegurar consistencia tras todo lo anterior.
                obj.refresh_from_db()
                obj.save()
            messages.success(request, "Liquidación guardada y recalculada.")
            return redirect("payroll:entry_edit", pk=entry.pk)
    else:
        form = PayrollEntryForm(instance=entry)
        extras_set = PayrollExtraordinaryFormSet(instance=entry, prefix="extras")
        alloc_set = PayrollAllocationFormSet(instance=entry, prefix="allocs")

    return render(request, "payroll/entry_form.html", {
        "form": form,
        "extras_set": extras_set,
        "alloc_set": alloc_set,
        "entry": entry,
    })


# ---------------------------------------------------------------------------
# Carga social (Turno D)
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class SocialChargesPaymentListView(ListView):
    model = SocialChargesPayment
    template_name = "payroll/social_charges_list.html"
    paginate_by = 50
    context_object_name = "payments"

    def get_queryset(self):
        return super().get_queryset().select_related("company", "currency")


@login_required
def social_charges_create(request):
    if request.method == "POST":
        form = SocialChargesPaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.created_by = request.user
                payment.save()
                # El signal post_save dispara el prorrateo. Lo corremos
                # explícitamente acá también para capturar el resultado y
                # mostrarlo en el detail.
                result = SocialChargesProrateService.prorate(payment)
            messages.success(
                request,
                f"Pago registrado. {result.allocations_updated} imputación(es) prorrateadas.",
            )
            return redirect("payroll:social_charges_detail", pk=payment.pk)
    else:
        form = SocialChargesPaymentForm()
    return render(request, "payroll/social_charges_form.html", {"form": form, "payment": None})


@login_required
def social_charges_detail(request, pk: int):
    payment = get_object_or_404(
        SocialChargesPayment.objects.select_related("company", "currency"), pk=pk,
    )
    # Re-correr el cálculo para mostrar resumen actualizado (no escribe nada
    # nuevo en DB si los datos no cambiaron — es idempotente).
    result = SocialChargesProrateService.prorate(payment)
    return render(request, "payroll/social_charges_detail.html", {
        "payment": payment,
        "result": result,
    })
