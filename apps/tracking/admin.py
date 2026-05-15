from django.contrib import admin

from .models import ProjectExecutionSnapshot, ProjectForecast, TaskExecution


@admin.register(ProjectExecutionSnapshot)
class ProjectExecutionSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "snapshot_date", "total_cost", "currency")
    list_filter = ("project",)
    date_hierarchy = "snapshot_date"
    readonly_fields = (
        "total_cost", "total_materials_cost",
        "total_labor_internal_cost", "total_labor_subcontract_cost",
        "total_social_charges_real", "total_social_charges_estimated",
        "breakdown",
    )
    autocomplete_fields = ("project", "currency")


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    list_display = ("project", "task", "planned_quantity", "actual_quantity",
                    "planned_cost", "actual_cost", "status")
    list_filter = ("status", "project")
    search_fields = ("project__name", "task__name")
    autocomplete_fields = ("project", "task")
    readonly_fields = ("last_computed_at",)


@admin.register(ProjectForecast)
class ProjectForecastAdmin(admin.ModelAdmin):
    list_display = ("project", "forecast_date", "forecasted_total_cost", "forecasted_completion_date")
    list_filter = ("project",)
    date_hierarchy = "forecast_date"
    autocomplete_fields = ("project",)
