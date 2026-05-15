from django.contrib import admin

from .models import ImportLog


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ("importer_label", "filename", "status", "rows_total", "rows_ok", "rows_error", "user", "created_at")
    list_filter = ("importer_slug", "status")
    search_fields = ("filename", "summary")
    readonly_fields = ("errors",)
