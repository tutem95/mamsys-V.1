from django.contrib import admin

from .models import Budget, BudgetItem


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0
    autocomplete_fields = ("task",)
    fields = ("task", "quantity", "unit_cost", "total_cost", "order")
    readonly_fields = ("unit_cost", "total_cost")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("project", "version", "status", "currency", "total_with_margin", "approved_at")
    list_filter = ("status", "project")
    search_fields = ("project__name", "name")
    autocomplete_fields = ("project", "currency", "exchange_rate_type")
    readonly_fields = (
        "pricing_date", "exchange_rate_value",
        "materials_cost", "labor_cost", "subcontracts_cost",
        "total_with_margin", "total_in_ars", "total_in_usd",
        "approved_by", "approved_at",
    )
    inlines = [BudgetItemInline]


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    list_display = ("budget", "task", "quantity", "unit_cost", "total_cost")
    search_fields = ("budget__project__name", "task__name")
    autocomplete_fields = ("budget", "task")
