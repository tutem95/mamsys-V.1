from django.contrib import admin

from .models import ExchangeRate, ExchangeRateType, Price


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


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("item", "amount", "currency", "effective_date", "source", "is_reference")
    list_filter = ("source", "is_reference", "currency")
    search_fields = ("notes",)
    date_hierarchy = "effective_date"
    readonly_fields = ("content_type", "object_id")
