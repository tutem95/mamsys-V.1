from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Purchase, PurchaseItem


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = (
            "purchase_type", "document_type", "document_number", "invoice_date",
            "is_subcontract",
            "supplier", "supplier_email", "company",
            "project", "rubro", "subrubro", "business_component",
            "detail", "main_item_description",
            "original_currency",
            "amount_without_tax", "iva_21", "iva_10_5", "perc_iibb", "total_amount",
            "payment_method", "week_to_pay", "due_date", "status",
            "notes",
        )
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "detail": forms.TextInput(),
            "main_item_description": forms.TextInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = (
            "material", "subcontract", "item_description",
            "quantity", "unit", "unit_price",
            "subrubro", "tracking_category",
            "notes",
        )
        widgets = {
            "item_description": forms.TextInput(),
            "notes": forms.TextInput(),
        }


PurchaseItemFormSet = inlineformset_factory(
    Purchase, PurchaseItem,
    form=PurchaseItemForm,
    extra=3, can_delete=True,
)
