from django.contrib import admin

from .models import (
    EmergencyContact,
    Employee,
    EmployeeBanking,
    EmployeePersonalData,
    PayrollEntry,
    PayrollPeriod,
    PositionPlus,
)


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


class PositionPlusInline(admin.TabularInline):
    model = PositionPlus
    extra = 0
    autocomplete_fields = ("position",)


class PayrollEntryInline(admin.TabularInline):
    model = PayrollEntry
    extra = 0
    fields = ("employee", "value_jornal", "days_worked", "gross", "net", "bank_amount", "cash_amount")
    readonly_fields = ("gross", "net")
    autocomplete_fields = ("employee",)


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("__str__", "company", "start_date", "end_date", "status")
    list_filter = ("status", "company", "year", "month")
    search_fields = ("talonario_name", "company__name")
    date_hierarchy = "start_date"
    inlines = [PositionPlusInline, PayrollEntryInline]


@admin.register(PayrollEntry)
class PayrollEntryAdmin(admin.ModelAdmin):
    list_display = ("payroll_period", "employee", "value_jornal", "days_worked", "gross", "net")
    list_filter = ("payroll_period__status", "payroll_period__year", "payroll_period__month")
    search_fields = ("employee__personal_data__last_name", "employee__personal_data__first_name")
    autocomplete_fields = ("employee", "payroll_period")
    readonly_fields = (
        "attendance_subtotal", "hours_subtotal", "presentismo_subtotal",
        "extraordinary_subtotal", "gross", "net",
        "overtime_amount", "cash_amount",
    )
