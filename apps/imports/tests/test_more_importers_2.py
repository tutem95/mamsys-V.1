"""Tests para UnitImporter y PayrollPeriodImporter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Unit
from apps.companies.models import Company
from apps.imports.importers import PayrollPeriodImporter, UnitImporter
from apps.payroll.models import Employee, EmployeePersonalData, PayrollEntry, PayrollPeriod


# ---------------------------------------------------------------------------
# UnitImporter
# ---------------------------------------------------------------------------


def test_unit_creates_with_category(tenant) -> None:
    rows = [
        {"symbol": "m2", "name": "Metro cuadrado", "category": "area"},
        {"symbol": "kg", "name": "Kilogramo", "category": "weight"},
        {"symbol": "JORNAL", "name": "Jornal", "category": "time"},
    ]
    result = UnitImporter().run(rows, dry_run=False)
    assert result.rows_created == 3
    assert Unit.objects.get(symbol="m2").category == "area"
    assert Unit.objects.get(symbol="JORNAL").category == "time"


def test_unit_unknown_category_defaults_to_other(tenant) -> None:
    rows = [{"symbol": "m2", "name": "Metro cuadrado", "category": "INEXISTENTE"}]
    result = UnitImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    assert Unit.objects.get(symbol="m2").category == "other"


def test_unit_updates_existing(tenant) -> None:
    Unit.objects.create(symbol="m2", name="Viejo", category=Unit.Category.OTHER)
    rows = [{"symbol": "m2", "name": "Nuevo", "category": "area"}]
    result = UnitImporter().run(rows, dry_run=False)
    assert result.rows_updated == 1
    u = Unit.objects.get(symbol="m2")
    assert u.name == "Nuevo"
    assert u.category == "area"


def test_unit_rejects_empty_symbol(tenant) -> None:
    rows = [{"symbol": "", "name": "Algo"}]
    result = UnitImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


# ---------------------------------------------------------------------------
# PayrollPeriodImporter
# ---------------------------------------------------------------------------


def _seed_company_and_employees(tenant):
    company = Company.objects.create(name="PASFAS SA")
    emp1 = Employee.objects.create(company=company, internal_id="EMP-001")
    EmployeePersonalData.objects.create(employee=emp1, first_name="Juan", last_name="Pérez")
    emp2 = Employee.objects.create(company=company, internal_id="EMP-002")
    EmployeePersonalData.objects.create(employee=emp2, first_name="Ana", last_name="López")
    return company, emp1, emp2


def test_payroll_period_creates_with_two_employees(tenant) -> None:
    _seed_company_and_employees(tenant)
    rows = [
        {
            "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
            "start_date": "2026-05-01", "end_date": "2026-05-15",
            "working_days": "10", "saturdays": "2", "total_days": "12",
            "plus_overtime_pct": "12", "plus_presentismo_pct": "2.30",
            "employee_internal_id": "EMP-001",
            "value_jornal": "25000", "days_worked": "12", "bank_amount": "200000",
        },
        {
            "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
            "start_date": "2026-05-01", "end_date": "2026-05-15",
            "employee_internal_id": "EMP-002",
            "value_jornal": "22000", "days_worked": "12",
        },
    ]
    result = PayrollPeriodImporter().run(rows, dry_run=False)
    assert result.rows_total == 1
    assert result.rows_created == 1
    assert result.rows_error == 0

    period = PayrollPeriod.objects.get(year=2026, month=5, period_number=1)
    assert period.total_days == 12
    assert period.entries.count() == 2

    entry = period.entries.get(employee__internal_id="EMP-001")
    assert entry.value_jornal == Decimal("25000.00")
    # recalculate() debe haber calculado el gross.
    assert entry.gross > 0
    assert entry.net > 0


def test_payroll_period_rejects_unknown_company(tenant) -> None:
    rows = [{
        "company": "NO EXISTE", "year": "2026", "month": "5", "period_number": "1",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
    }]
    result = PayrollPeriodImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_payroll_period_rejects_invalid_period_number(tenant) -> None:
    Company.objects.create(name="PASFAS SA")
    rows = [{
        "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "3",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
    }]
    result = PayrollPeriodImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_payroll_period_reimport_updates_existing(tenant) -> None:
    company, emp1, _ = _seed_company_and_employees(tenant)
    rows_v1 = [{
        "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
        "employee_internal_id": "EMP-001",
        "value_jornal": "20000", "days_worked": "12",
    }]
    PayrollPeriodImporter().run(rows_v1, dry_run=False)
    assert PayrollPeriod.objects.filter(year=2026, month=5).count() == 1

    rows_v2 = [{
        "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
        "plus_presentismo_pct": "5",
        "employee_internal_id": "EMP-001",
        "value_jornal": "30000", "days_worked": "12",
    }]
    result = PayrollPeriodImporter().run(rows_v2, dry_run=False)
    assert result.rows_updated == 1
    period = PayrollPeriod.objects.get(year=2026, month=5, period_number=1)
    assert period.plus_presentismo_pct == Decimal("5")
    entry = period.entries.get(employee=emp1)
    assert entry.value_jornal == Decimal("30000.00")


def test_payroll_period_dry_run_does_not_persist(tenant) -> None:
    _seed_company_and_employees(tenant)
    rows = [{
        "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
        "employee_internal_id": "EMP-001",
        "value_jornal": "25000",
    }]
    result = PayrollPeriodImporter().run(rows, dry_run=True)
    assert result.rows_created == 1
    assert not PayrollPeriod.objects.filter(year=2026).exists()


def test_payroll_period_unknown_employee_fails_atomic(tenant) -> None:
    Company.objects.create(name="PASFAS SA")
    rows = [{
        "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
        "start_date": "2026-05-01", "end_date": "2026-05-15",
        "employee_internal_id": "EMP-NOPE",
        "value_jornal": "25000",
    }]
    result = PayrollPeriodImporter().run(rows, dry_run=False)
    assert result.rows_error == 1
    # La PayrollPeriod NO debe haberse creado por la transacción atómica.
    assert not PayrollPeriod.objects.filter(year=2026).exists()


def test_payroll_period_groups_split_correctly(tenant) -> None:
    """Filas con distintos (company, year, month, period_number) son grupos distintos."""
    _seed_company_and_employees(tenant)
    rows = [
        {
            "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "1",
            "start_date": "2026-05-01", "end_date": "2026-05-15",
            "employee_internal_id": "EMP-001", "value_jornal": "25000",
        },
        {
            "company": "PASFAS SA", "year": "2026", "month": "5", "period_number": "2",
            "start_date": "2026-05-16", "end_date": "2026-05-31",
            "employee_internal_id": "EMP-001", "value_jornal": "25000",
        },
    ]
    result = PayrollPeriodImporter().run(rows, dry_run=False)
    assert result.rows_total == 2
    assert result.rows_created == 2
    assert PayrollPeriod.objects.filter(year=2026, month=5).count() == 2
