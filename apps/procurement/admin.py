from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    autocomplete_fields = ("material", "subcontract", "unit", "subrubro")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_date", "supplier", "company", "project",
        "rubro", "total_amount", "original_currency", "status",
    )
    list_filter = ("status", "purchase_type", "is_subcontract", "company", "rubro")
    search_fields = ("document_number", "supplier__name", "detail", "notes")
    date_hierarchy = "invoice_date"
    autocomplete_fields = ("supplier", "company", "project", "rubro", "subrubro", "business_component")
    inlines = [PurchaseItemInline]


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ("purchase", "material", "subcontract", "quantity", "unit_price", "total")
    autocomplete_fields = ("purchase", "material", "subcontract", "unit")
