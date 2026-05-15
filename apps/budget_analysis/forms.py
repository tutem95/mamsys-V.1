from __future__ import annotations

from django import forms
from django.utils.timezone import localdate

from .models import BudgetVsActualReport


class GenerateCrossForm(forms.Form):
    """Form para correr un cruce sobre un Budget. No persiste (la view crea el report)."""

    project = forms.ModelChoiceField(queryset=None, label="Obra")
    budget = forms.ModelChoiceField(queryset=None, label="Presupuesto")
    cutoff_date = forms.DateField(
        label="Fecha de corte",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=localdate,
    )
    in_currency = forms.ModelChoiceField(queryset=None, label="Moneda")
    rate_type = forms.ModelChoiceField(queryset=None, label="Tipo de cotización", required=False)
    save_report = forms.BooleanField(
        label="Guardar reporte (para historial)", required=False, initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.budgets.models import Budget
        from apps.currencies.models import Currency
        from apps.pricing.models import ExchangeRateType
        from apps.projects.models import Project
        self.fields["project"].queryset = Project.objects.filter(is_archived=False).order_by("name")
        self.fields["budget"].queryset = Budget.objects.select_related("project").order_by("-project__name", "-version")
        self.fields["in_currency"].queryset = Currency.objects.filter(active=True).order_by("code")
        self.fields["rate_type"].queryset = ExchangeRateType.objects.filter(active=True).order_by("name")
