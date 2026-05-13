from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import (
    Employee,
    EmployeeBanking,
    EmployeePersonalData,
    EmergencyContact,
    PayrollEntry,
    PayrollPeriod,
    PositionPlus,
)


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "internal_id",
            "company", "status", "position", "primary_rubro",
            "boss",
            "hire_date", "termination_date",
            "arca_registered",
            "teams",
        )
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "termination_date": forms.DateInput(attrs={"type": "date"}),
            "teams": forms.SelectMultiple(attrs={"size": 5}),
        }


class EmployeePersonalDataForm(forms.ModelForm):
    class Meta:
        model = EmployeePersonalData
        fields = (
            "first_name", "last_name",
            "document_type", "document_number", "cuil",
            "nationality", "birth_date", "marital_status", "children_count",
            "phone_landline", "phone_mobile", "email", "address",
        )
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.TextInput(),
        }


class EmployeeBankingForm(forms.ModelForm):
    class Meta:
        model = EmployeeBanking
        fields = ("bank", "cbu", "cvu_mercado_libre")


EmergencyContactFormSet = inlineformset_factory(
    Employee, EmergencyContact,
    fields=("full_name", "relationship", "phone"),
    extra=2, can_delete=True,
)


# ---------------------------------------------------------------------------
# Quincenas (Turno B)
# ---------------------------------------------------------------------------


class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = (
            "company",
            "period_number", "month", "year",
            "start_date", "end_date", "talonario_name",
            "working_days", "saturdays", "holidays", "total_days",
            "hours_weekday", "hours_saturday", "total_hours",
            "plus_overtime_pct", "plus_presentismo_pct",
            "status",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class PositionPlusForm(forms.ModelForm):
    class Meta:
        model = PositionPlus
        fields = ("position", "amount", "currency")


PositionPlusFormSet = inlineformset_factory(
    PayrollPeriod, PositionPlus,
    form=PositionPlusForm,
    extra=2, can_delete=True,
)


class PayrollEntryForm(forms.ModelForm):
    """Edición individual de una entrada de quincena."""

    class Meta:
        model = PayrollEntry
        fields = (
            "currency", "value_jornal",
            "days_worked", "absences", "justified_absences",
            "vacations", "vacations_amount", "vacations_detail",
            "late_hours", "late_hours_amount", "late_hours_detail",
            "overtime_hours",
            "bank_amount",
            "bills_manual_override",
            "bills_1000", "bills_500", "bills_200", "bills_100",
            "bills_50", "bills_20", "bills_10",
            "receipt_observations", "internal_notes",
            "suspended",
        )
        widgets = {
            "vacations_detail": forms.TextInput(),
            "late_hours_detail": forms.TextInput(),
            "receipt_observations": forms.TextInput(),
            "internal_notes": forms.Textarea(attrs={"rows": 2}),
        }


class PayrollEntryQuickForm(forms.ModelForm):
    """Form chiquito tipo planilla: solo los campos que se cargan rápido."""

    class Meta:
        model = PayrollEntry
        fields = ("value_jornal", "days_worked", "overtime_hours", "vacations_amount", "late_hours_amount", "bank_amount")
