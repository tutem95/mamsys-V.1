from __future__ import annotations

from django import forms

from .models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "legal_name", "tax_id", "iva_condition", "iibb_number", "fiscal_address")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ej: PASFAS SA"}),
            "legal_name": forms.TextInput(attrs={"placeholder": "Razón social legal"}),
            "tax_id": forms.TextInput(attrs={"placeholder": "30-12345678-9"}),
            "iibb_number": forms.TextInput(),
            "fiscal_address": forms.TextInput(),
        }
