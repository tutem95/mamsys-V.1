from django.contrib import admin

from .models import (
    Bank,
    BusinessComponent,
    EmployeeStatus,
    ExtraordinaryConcept,
    Material,
    Position,
    ProjectStatus,
    Rubro,
    Subcontract,
    Subrubro,
    Supplier,
    Team,
    TrackingCategory,
    Unit,
)


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


@admin.register(ProjectStatus)
class ProjectStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "order")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "order")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active", "order")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(ExtraordinaryConcept)
class ExtraordinaryConceptAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "active")
    list_filter = ("type", "active")
    search_fields = ("name",)


@admin.register(TrackingCategory)
class TrackingCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "active")
    list_filter = ("active",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "tax_id", "active")
    list_filter = ("active", "category")
    search_fields = ("name", "code", "tax_id", "contact_name")
    filter_horizontal = ("rubros",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "rubro", "subrubro", "unit", "last_known_price", "active")
    list_filter = ("active", "rubro")
    search_fields = ("name",)
    autocomplete_fields = ("rubro", "subrubro", "unit")


@admin.register(Subcontract)
class SubcontractAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "typical_supplier", "last_known_price", "active")
    list_filter = ("active", "unit")
    search_fields = ("name",)
    autocomplete_fields = ("unit", "typical_supplier")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "leader", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    autocomplete_fields = ("leader",)
