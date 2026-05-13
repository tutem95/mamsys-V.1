from django.contrib import admin

from .models import Purchase, PurchaseItem, PurchasePayment


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    autocomplete_fields = ("material", "subcontract", "unit", "subrubro")


class PurchasePaymentInline(admin.TabularInline):
    model = PurchasePayment
    extra = 0
    fields = ("payment_date", "amount", "currency", "payment_method", "reference")


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
    inlines = [PurchaseItemInline, PurchasePaymentInline]


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ("purchase", "material", "subcontract", "quantity", "unit_price", "total")
    autocomplete_fields = ("purchase", "material", "subcontract", "unit")


@admin.register(PurchasePayment)
class PurchasePaymentAdmin(admin.ModelAdmin):
    list_display = ("purchase", "payment_date", "amount", "currency", "payment_method")
    list_filter = ("currency", "payment_method")
    search_fields = ("reference", "purchase__document_number")
    date_hierarchy = "payment_date"
    autocomplete_fields = ("purchase",)
