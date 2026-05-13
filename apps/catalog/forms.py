from __future__ import annotations

from django import forms

from .models import BusinessComponent, Rubro, Subrubro, Unit


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
