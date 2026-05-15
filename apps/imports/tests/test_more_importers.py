"""Tests para Supplier, Employee y ExchangeRate importers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Bank, EmployeeStatus, Position, Rubro, Supplier
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.imports.importers import (
    EmployeeImporter,
    ExchangeRateImporter,
    SupplierImporter,
)
from apps.payroll.models import Employee
from apps.pricing.models import ExchangeRate, ExchangeRateType


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


def test_supplier_creates_with_rubros(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA")
    Rubro.objects.create(name="ALBAÑILERIA")
    rows = [{
        "name": "CORRALON CENTRO", "code": "CRN001", "category": "CORRALON",
        "rubros": "ESTRUCTURA|ALBAÑILERIA",
        "contact_name": "Juan", "email": "info@corralon.com",
        "phone": "11-1234", "address": "Av Siempre Viva 123",
        "tax_id": "30-12345678-9", "notes": "Proveedor de confianza",
    }]
    result = SupplierImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    s = Supplier.objects.get(name="CORRALON CENTRO")
    assert s.code == "CRN001"
    assert s.category == "CORRALON"
    assert set(s.rubros.values_list("name", flat=True)) == {"ESTRUCTURA", "ALBAÑILERIA"}


def test_supplier_rejects_missing_rubro(tenant) -> None:
    rows = [{"name": "X", "rubros": "INEXISTENTE"}]
    result = SupplierImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_supplier_updates_existing_replaces_rubros(tenant) -> None:
    a = Rubro.objects.create(name="A")
    b = Rubro.objects.create(name="B")
    Supplier.objects.create(name="S", code="OLD")
    rows = [{"name": "S", "code": "NEW", "rubros": "A|B"}]
    result = SupplierImporter().run(rows, dry_run=False)
    assert result.rows_updated == 1
    s = Supplier.objects.get(name="S")
    assert s.code == "NEW"
    assert set(s.rubros.values_list("name", flat=True)) == {"A", "B"}


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------


def test_employee_creates_with_company_and_position(tenant) -> None:
    Company.objects.create(name="PASFAS SA")
    Position.objects.create(name="Oficial")
    EmployeeStatus.objects.create(name="Activo")
    rows = [{
        "first_name": "Mateo", "last_name": "Gomez", "company": "PASFAS SA",
        "internal_id": "EMP-001", "position": "Oficial", "status": "Activo",
        "hire_date": "2024-03-15", "arca_registered": "si",
        "document_type": "DNI", "document_number": "30123456",
        "cuil": "20-30123456-1", "birth_date": "01/06/1990",
        "phone_mobile": "11-5555-1111", "email": "mateo@demo.com",
    }]
    result = EmployeeImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    emp = Employee.objects.get(internal_id="EMP-001")
    assert emp.position.name == "Oficial"
    assert emp.status.name == "Activo"
    assert emp.arca_registered is True
    assert emp.hire_date == date(2024, 3, 15)
    assert emp.personal_data.cuil == "20-30123456-1"
    assert emp.personal_data.birth_date == date(1990, 6, 1)


def test_employee_rejects_missing_company(tenant) -> None:
    rows = [{
        "first_name": "X", "last_name": "Y", "company": "NOEXISTE",
    }]
    result = EmployeeImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_employee_updates_existing_by_internal_id(tenant) -> None:
    company = Company.objects.create(name="PASFAS SA")
    Employee.objects.create(company=company, internal_id="EMP-007")
    rows = [{
        "first_name": "Nuevo", "last_name": "Nombre", "company": "PASFAS SA",
        "internal_id": "EMP-007",
    }]
    result = EmployeeImporter().run(rows, dry_run=False)
    assert result.rows_updated == 1
    assert Employee.objects.filter(internal_id="EMP-007").count() == 1
    emp = Employee.objects.get(internal_id="EMP-007")
    assert emp.personal_data.first_name == "Nuevo"


def test_employee_banking_attached_when_bank_provided(tenant) -> None:
    Company.objects.create(name="PASFAS SA")
    Bank.objects.create(name="Galicia")
    rows = [{
        "first_name": "Ana", "last_name": "Lopez", "company": "PASFAS SA",
        "bank": "Galicia", "cbu": "0070000000000000000001",
    }]
    result = EmployeeImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    emp = Employee.objects.filter(personal_data__last_name="Lopez").first()
    assert emp.banking.bank.name == "Galicia"
    assert emp.banking.cbu == "0070000000000000000001"


# ---------------------------------------------------------------------------
# ExchangeRate
# ---------------------------------------------------------------------------


def test_exchange_rate_creates_for_existing_type(tenant) -> None:
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    rows = [
        {"rate_type": "BNA", "date": "2026-05-13", "rate": "1230.50", "source": "imported"},
        {"rate_type": "BNA", "date": "14/05/2026", "rate": "1235,75", "source": ""},
    ]
    result = ExchangeRateImporter().run(rows, dry_run=False)
    assert result.rows_created == 2
    r1 = ExchangeRate.objects.get(rate_type__name="BNA", date=date(2026, 5, 13))
    assert r1.rate == Decimal("1230.50")
    r2 = ExchangeRate.objects.get(rate_type__name="BNA", date=date(2026, 5, 14))
    assert r2.rate == Decimal("1235.75")


def test_exchange_rate_rejects_unknown_type(tenant) -> None:
    rows = [{"rate_type": "INEXISTENTE", "date": "2026-05-13", "rate": "1000"}]
    result = ExchangeRateImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_exchange_rate_rejects_bad_date(tenant) -> None:
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    rows = [{"rate_type": "BNA", "date": "ayer", "rate": "1000"}]
    result = ExchangeRateImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_exchange_rate_updates_existing(tenant) -> None:
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    bna = ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    rows = [{"rate_type": "BNA", "date": "2026-05-13", "rate": "1500"}]
    result = ExchangeRateImporter().run(rows, dry_run=False)
    assert result.rows_updated == 1
    r = ExchangeRate.objects.get(rate_type=bna, date=date(2026, 5, 13))
    assert r.rate == Decimal("1500")
