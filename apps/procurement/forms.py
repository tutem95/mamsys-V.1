from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Purchase, PurchaseItem, PurchasePayment


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


class PurchasePaymentForm(forms.ModelForm):
    class Meta:
        model = PurchasePayment
        fields = ("payment_date", "amount", "currency", "payment_method", "reference", "notes")
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01"}),
            "notes": forms.TextInput(),
        }

    def __init__(self, *args, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-cargar moneda con la de la compra si está disponible.
        if purchase is not None and not self.is_bound:
            self.fields["currency"].initial = purchase.original_currency
