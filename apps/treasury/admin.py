from django.contrib import admin

from .models import TreasuryEntry


@admin.register(TreasuryEntry)
class TreasuryEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "entry_type", "category", "company", "bank_account",
                     "amount", "currency", "is_reconciled")
    list_filter = ("entry_type", "category", "is_reconciled", "company", "bank_account")
    search_fields = ("description", "notes")
    date_hierarchy = "date"
    autocomplete_fields = (
        "company", "bank_account", "counterpart_account",
        "currency", "counterpart_currency",
        "project",
        "source_purchase_payment", "source_social_charges_payment", "source_payroll_period",
    )
    readonly_fields = ("source_purchase_payment", "source_social_charges_payment", "source_payroll_period")
