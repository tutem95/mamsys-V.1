from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Budget, BudgetItem


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = (
            "project", "name", "version",
            "currency", "exchange_rate_type",
            "margin_pct",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class BudgetItemForm(forms.ModelForm):
    class Meta:
        model = BudgetItem
        fields = ("task", "quantity", "order", "notes")
        widgets = {"notes": forms.TextInput()}


BudgetItemFormSet = inlineformset_factory(
    Budget, BudgetItem,
    form=BudgetItemForm,
    extra=3, can_delete=True,
)
