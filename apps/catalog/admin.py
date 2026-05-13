from django.contrib import admin

from .models import BusinessComponent, Rubro, Subrubro, Unit


@admin.register(Rubro)
class RubroAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active", "order")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("order", "name")


@admin.register(Subrubro)
class SubrubroAdmin(admin.ModelAdmin):
    list_display = ("rubro", "name", "code", "active", "order")
    list_filter = ("active", "rubro")
    search_fields = ("name", "code", "rubro__name")
    ordering = ("rubro__name", "order", "name")
    autocomplete_fields = ("rubro",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "category", "active")
    list_filter = ("active", "category")
    search_fields = ("name", "symbol")
    ordering = ("symbol",)


@admin.register(BusinessComponent)
class BusinessComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active", "order")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("order", "name")
