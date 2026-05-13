from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import EmailVerificationToken, PasswordResetToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "email_verified", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "email_verified")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "phone")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "email_verified",
                                  "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "created_at")}),
    )
    readonly_fields = ("last_login", "created_at")
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )


admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)
