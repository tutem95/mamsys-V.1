from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "content_type", "object_id")
    list_filter = ("action", "content_type")
    search_fields = ("object_id",)
    readonly_fields = ("user", "timestamp", "action", "content_type", "object_id", "changes")
    date_hierarchy = "timestamp"
