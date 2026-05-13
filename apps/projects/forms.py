from __future__ import annotations

from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            "name", "code", "company", "status",
            "address",
            "start_date", "estimated_end_date", "actual_end_date",
            "project_manager",
            "notes",
            "is_archived",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "estimated_end_date": forms.DateInput(attrs={"type": "date"}),
            "actual_end_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Project managers: usuarios con membership activa en esta org. Como
        # vivimos en el tenant y Membership es shared (schema_name='public'),
        # filtramos por orgs que comparten el slug; en la práctica simplificamos
        # mostrando todos los usuarios autenticables. Se afina cuando agreguemos
        # el helper get_accessible_users() en apps.permissions.
        from apps.accounts.models import User

        self.fields["project_manager"].queryset = User.objects.filter(is_active=True).order_by("email")
        self.fields["project_manager"].required = False
