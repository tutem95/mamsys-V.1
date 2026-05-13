from django.contrib import admin

from .models import ExchangeRate, ExchangeRateType


@admin.register(ExchangeRateType)
class ExchangeRateTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "currency_from", "currency_to", "is_default", "calculation_type", "active")
    list_filter = ("active", "calculation_type", "is_default")
    search_fields = ("name",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("rate_type", "date", "rate", "source")
    list_filter = ("source", "rate_type")
    search_fields = ("rate_type__name", "notes")
    date_hierarchy = "date"
    ordering = ("-date",)
