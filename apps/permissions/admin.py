from django.contrib import admin

from .models import ObjectAccess, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_system", "updated_at")
    list_filter = ("organization", "is_system")
    search_fields = ("name", "organization__name")


@admin.register(ObjectAccess)
class ObjectAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "content_type", "object_id", "can_view", "can_edit")
    list_filter = ("organization", "content_type", "can_edit")
    search_fields = ("user__email",)
