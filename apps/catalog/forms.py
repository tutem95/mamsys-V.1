from __future__ import annotations

from django import forms

from .models import (
    Bank,
    BusinessComponent,
    EmployeeStatus,
    ExtraordinaryConcept,
    Material,
    Position,
    ProjectStatus,
    Rubro,
    Subcontract,
    Subrubro,
    Supplier,
    TrackingCategory,
    Unit,
)


class RubroForm(forms.ModelForm):
    class Meta:
        model = Rubro
        fields = ("name", "code", "active", "order")


class SubrubroForm(forms.ModelForm):
    class Meta:
        model = Subrubro
        fields = ("rubro", "name", "code", "active", "order")


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ("name", "symbol", "category", "active", "order")


class BusinessComponentForm(forms.ModelForm):
    class Meta:
        model = BusinessComponent
        fields = ("name", "code", "active", "order")


class ProjectStatusForm(forms.ModelForm):
    class Meta:
        model = ProjectStatus
        fields = ("name", "code", "active", "order")


class EmployeeStatusForm(forms.ModelForm):
    class Meta:
        model = EmployeeStatus
        fields = ("name", "code", "active", "order")


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ("name", "code", "active", "order")


class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ("name", "code", "active", "order")


class ExtraordinaryConceptForm(forms.ModelForm):
    class Meta:
        model = ExtraordinaryConcept
        fields = ("type", "name", "code", "active", "order")


class TrackingCategoryForm(forms.ModelForm):
    class Meta:
        model = TrackingCategory
        fields = ("name", "color", "code", "active", "order")
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "code", "name", "category",
            "rubros",
            "contact_name", "email", "phone", "address", "tax_id",
            "notes",
            "active", "order",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "rubros": forms.SelectMultiple(attrs={"size": 6}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = (
            "name", "code", "rubro", "subrubro", "unit",
            "description", "last_known_price",
            "active", "order",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class SubcontractForm(forms.ModelForm):
    class Meta:
        model = Subcontract
        fields = (
            "name", "code", "unit", "typical_supplier",
            "description", "last_known_price",
            "active", "order",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}
