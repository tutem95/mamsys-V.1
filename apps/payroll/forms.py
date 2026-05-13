from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import (
    Employee,
    EmployeeBanking,
    EmployeePersonalData,
    EmergencyContact,
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
