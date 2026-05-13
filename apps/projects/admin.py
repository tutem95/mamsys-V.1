from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "company", "status", "start_date", "is_archived")
    list_filter = ("is_archived", "company", "status")
    search_fields = ("name", "code", "address")
    autocomplete_fields = ("company", "status", "project_manager")
    date_hierarchy = "start_date"
