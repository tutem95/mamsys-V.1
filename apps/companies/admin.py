from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_id", "iva_condition", "active")
    list_filter = ("iva_condition", "active")
    search_fields = ("name", "legal_name", "tax_id")
