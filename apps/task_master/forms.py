from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Mix, MixComponent, Task, TaskComponent


class MixForm(forms.ModelForm):
    class Meta:
        model = Mix
        fields = ("name", "code", "output_unit", "description", "active")
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class MixComponentForm(forms.ModelForm):
    class Meta:
        model = MixComponent
        fields = ("material", "sub_mix", "quantity_per_unit", "input_unit", "notes")
        widgets = {"notes": forms.TextInput()}


MixComponentFormSet = inlineformset_factory(
    Mix, MixComponent, form=MixComponentForm, extra=3, can_delete=True,
    fk_name="mix",
)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("code", "name", "rubro", "subrubro", "output_unit", "description", "active")
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class TaskComponentForm(forms.ModelForm):
    class Meta:
        model = TaskComponent
        fields = (
            "source_type",
            "material", "position", "subcontract", "sub_mix", "sub_task",
            "quantity_per_unit", "input_unit",
            "classification", "detail",
        )
        widgets = {"detail": forms.TextInput()}


TaskComponentFormSet = inlineformset_factory(
    Task, TaskComponent,
    form=TaskComponentForm,
    extra=3, can_delete=True,
    fk_name="task",
)
