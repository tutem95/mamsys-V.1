from django.contrib import admin

from .models import Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "active")
    list_filter = ("active",)
    search_fields = ("code", "name")
    ordering = ("code",)
