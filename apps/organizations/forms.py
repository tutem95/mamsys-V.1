from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from apps.accounts.models import User

from .models import Organization


class OrganizationSignupForm(forms.Form):
    """Sign-up público: crea Organization + Domain + primer User Admin."""

    organization_name = forms.CharField(
        label="Nombre de la empresa",
        max_length=120,
    )
    organization_slug = forms.SlugField(
        label="Subdominio",
        max_length=40,
        help_text="Se usa para el acceso: <subdominio>.localhost en dev.",
    )
    tax_id = forms.CharField(label="CUIT", max_length=20, required=False)

    first_name = forms.CharField(label="Nombre", max_length=80)
    last_name = forms.CharField(label="Apellido", max_length=80)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput, min_length=10)
    password_confirm = forms.CharField(label="Repetir contraseña", widget=forms.PasswordInput)

    def clean_organization_slug(self) -> str:
        slug = slugify(self.cleaned_data["organization_slug"])
        if Organization.objects.filter(slug=slug).exists():
            raise forms.ValidationError("Ese subdominio ya está en uso.")
        if slug in {"www", "admin", "api", "public"}:
            raise forms.ValidationError("Ese subdominio está reservado.")
        return slug

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese email.")
        return email

    def clean(self) -> dict:
        data = super().clean()
        if data.get("password") and data.get("password_confirm"):
            if data["password"] != data["password_confirm"]:
                self.add_error("password_confirm", "Las contraseñas no coinciden.")
            else:
                validate_password(data["password"])
        return data
