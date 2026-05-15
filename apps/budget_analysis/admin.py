from django.contrib import admin

from .models import BudgetVsActualReport


@admin.register(BudgetVsActualReport)
class BudgetVsActualReportAdmin(admin.ModelAdmin):
    list_display = ("project", "budget", "cutoff_date", "in_currency",
                    "total_planned", "total_actual", "variance_amount", "variance_pct")
    list_filter = ("in_currency", "project")
    date_hierarchy = "cutoff_date"
    readonly_fields = ("data", "total_planned", "total_actual", "variance_amount", "variance_pct")
    autocomplete_fields = ("project", "budget")
