from __future__ import annotations

from django import forms

from .models import TreasuryEntry


class TreasuryEntryForm(forms.ModelForm):
    class Meta:
        model = TreasuryEntry
        fields = (
            "entry_type", "category",
            "date", "company",
            "bank_account", "counterpart_account",
            "amount", "currency",
            "counterpart_amount", "counterpart_currency", "exchange_rate_used",
            "project",
            "description", "notes",
        )
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.TextInput(),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
