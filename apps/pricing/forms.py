from __future__ import annotations

from django import forms

from .models import ExchangeRate, ExchangeRateType


class ExchangeRateTypeForm(forms.ModelForm):
    class Meta:
        model = ExchangeRateType
        fields = (
            "name", "currency_from", "currency_to",
            "calculation_type", "combination_formula",
            "is_default", "active", "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
            "combination_formula": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": '{"BNA": 0.7, "CCL": 0.3}',
            }),
        }


class ExchangeRateForm(forms.ModelForm):
    """Form para cargar una cotización puntual en un ExchangeRateType."""

    class Meta:
        model = ExchangeRate
        fields = ("date", "rate", "source", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "rate": forms.NumberInput(attrs={"step": "0.0001", "placeholder": "Ej: 1230.50"}),
        }
