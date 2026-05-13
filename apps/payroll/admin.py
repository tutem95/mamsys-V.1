from django.contrib import admin

from .models import EmergencyContact, Employee, EmployeeBanking, EmployeePersonalData


class PersonalDataInline(admin.StackedInline):
    model = EmployeePersonalData
    extra = 0


class BankingInline(admin.StackedInline):
    model = EmployeeBanking
    extra = 0
    autocomplete_fields = ("bank",)


class EmergencyContactInline(admin.TabularInline):
    model = EmergencyContact
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "internal_id", "company", "position", "status", "hire_date", "arca_registered")
    list_filter = ("status", "company", "position", "arca_registered")
    search_fields = (
        "internal_id",
        "personal_data__first_name",
        "personal_data__last_name",
        "personal_data__document_number",
        "personal_data__cuil",
    )
    autocomplete_fields = ("company", "status", "position", "primary_rubro", "boss")
    filter_horizontal = ("teams",)
    inlines = [PersonalDataInline, BankingInline, EmergencyContactInline]
    date_hierarchy = "hire_date"


@admin.register(EmployeePersonalData)
class EmployeePersonalDataAdmin(admin.ModelAdmin):
    list_display = ("full_name", "document_type", "document_number", "cuil")
    search_fields = ("first_name", "last_name", "document_number", "cuil")


@admin.register(EmployeeBanking)
class EmployeeBankingAdmin(admin.ModelAdmin):
    list_display = ("employee", "bank", "cbu")
    search_fields = ("cbu", "cvu_mercado_libre")
    autocomplete_fields = ("employee", "bank")


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ("employee", "full_name", "relationship", "phone")
    search_fields = ("full_name",)
    autocomplete_fields = ("employee",)
