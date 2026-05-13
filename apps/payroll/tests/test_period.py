"""Quincena, plus por puesto, entradas y cálculos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import Position
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.payroll.models import (
    Employee,
    EmployeePersonalData,
    PayrollEntry,
    PayrollPeriod,
    PositionPlus,
    calculate_bills,
    pre_generate_entries_for_period,
    round_to_multiple_of_10,
)


# ---------------------------------------------------------------------------
# Helpers puros (no requieren DB)
# ---------------------------------------------------------------------------

def test_calculate_bills_uses_greedy() -> None:
    bills, remainder = calculate_bills(1340)
    assert bills == {1000: 1, 500: 0, 200: 1, 100: 1, 50: 0, 20: 2, 10: 0}
    assert remainder == 0


def test_calculate_bills_with_remainder() -> None:
    bills, remainder = calculate_bills(1345)
    # 1345 → 1×1000 + 1×200 + 1×100 + 0×50 + 2×20 + 0×10 = 1340; remainder = 5.
    assert remainder == 5


def test_round_to_multiple_of_10() -> None:
    assert round_to_multiple_of_10(Decimal("1234.56")) == Decimal("1230")
    assert round_to_multiple_of_10(Decimal("1235")) == Decimal("1240")
    assert round_to_multiple_of_10(Decimal("1239.99")) == Decimal("1240")


# ---------------------------------------------------------------------------
# Fixture compartido
# ---------------------------------------------------------------------------

def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    oficial = Position.objects.create(name="Oficial")
    ars = Currency.objects.get(code="ARS")
    emp = Employee.objects.create(company=company, position=oficial)
    EmployeePersonalData.objects.create(employee=emp, first_name="Juan", last_name="Pérez")
    return company, oficial, ars, emp


def _make_period(company, **kwargs) -> PayrollPeriod:
    defaults = dict(
        company=company,
        period_number=1, month=5, year=2026,
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 15),
        working_days=10, saturdays=2, holidays=0, total_days=12,
        hours_weekday=8, hours_saturday=7, total_hours=94,
        plus_overtime_pct=Decimal("12"),
        plus_presentismo_pct=Decimal("2.30"),
    )
    defaults.update(kwargs)
    return PayrollPeriod.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def test_period_unique_per_company_year_month_number(tenant) -> None:
    company, *_ = _setup(tenant)
    _make_period(company)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _make_period(company)


def test_position_plus_unique_per_period_position(tenant) -> None:
    company, oficial, ars, _emp = _setup(tenant)
    period = _make_period(company)
    PositionPlus.objects.create(payroll_period=period, position=oficial, amount=25, currency=ars)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PositionPlus.objects.create(payroll_period=period, position=oficial, amount=30, currency=ars)


def test_payroll_entry_unique_per_employee_per_period(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company)
    PayrollEntry.objects.create(payroll_period=period, employee=emp, currency=ars)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PayrollEntry.objects.create(payroll_period=period, employee=emp, currency=ars)


# ---------------------------------------------------------------------------
# Cálculos
# ---------------------------------------------------------------------------

def test_attendance_subtotal_is_days_times_jornal(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("12"),
    )
    assert e.attendance_subtotal == Decimal("12000.00")
    assert e.gross == Decimal("12000.00")
    # net redondeado a múltiplo de 10
    assert e.net == Decimal("12000")


def test_overtime_uses_plus_pct(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("12"), plus_presentismo_pct=Decimal("0"))
    # value_jornal=800, 8 horas/día → valor_hora=100. 5h extra × 100 × 1.12 = 560.
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("800"), days_worked=Decimal("10"),
        overtime_hours=Decimal("5"),
    )
    assert e.overtime_amount == Decimal("560.00")


def test_presentismo_applies_pct_on_gross(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("10"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("10"),
    )
    # gross = 10*1000 = 10000. presentismo = 10000 * 0.10 = 1000.
    assert e.presentismo_subtotal == Decimal("1000.00")
    assert e.net == Decimal("11000")


def test_position_plus_adds_per_day(tenant) -> None:
    company, oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    PositionPlus.objects.create(payroll_period=period, position=oficial, amount=Decimal("25"), currency=ars)
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("10"),
    )
    # gross = 10*1000 + 10*25 = 10250
    assert e.gross == Decimal("10250.00")


def test_late_hours_and_vacations_reduce_gross(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("10"),
        late_hours_amount=Decimal("500"),
        vacations_amount=Decimal("1000"),
    )
    # 10000 - 1000 - 500 = 8500
    assert e.gross == Decimal("8500.00")


def test_cash_amount_complements_bank_to_net(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("10"),
        bank_amount=Decimal("7000"),
    )
    # net=10000, bank=7000 → cash=3000
    assert e.cash_amount == Decimal("3000")


def test_bills_calculated_from_cash(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("100"), days_worked=Decimal("13"),
        bank_amount=Decimal("0"),
    )
    # net=1300 → cash=1300 → 1×1000 + 1×200 + 1×100
    assert e.cash_amount == Decimal("1300")
    assert e.bills_1000 == 1
    assert e.bills_200 == 1
    assert e.bills_100 == 1


def test_bills_manual_override_keeps_provided_values(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company, plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"))
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("100"), days_worked=Decimal("13"),
        bills_manual_override=True,
        bills_1000=2, bills_500=0,
    )
    assert e.bills_1000 == 2  # no se recalculó


def test_entry_takes_snapshot_on_create(tenant) -> None:
    company, oficial, ars, emp = _setup(tenant)
    period = _make_period(company)
    e = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
    )
    assert e.position_snapshot == "Oficial"
    assert e.company_snapshot == "PASFAS SA"


def test_entry_save_updates_last_known_salary_on_employee(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company)
    PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1234.56"), days_worked=Decimal("10"),
    )
    emp.refresh_from_db()
    assert emp.last_known_salary == Decimal("1234.56")
    assert emp.last_known_currency_id == ars.pk


# ---------------------------------------------------------------------------
# Pre-generación de entradas
# ---------------------------------------------------------------------------

def test_pre_generate_creates_entry_for_each_active_employee(tenant) -> None:
    company, _oficial, ars, emp1 = _setup(tenant)
    emp2 = Employee.objects.create(company=company)
    period = _make_period(company)

    created = pre_generate_entries_for_period(period)
    assert len(created) == 2
    assert PayrollEntry.objects.filter(payroll_period=period).count() == 2


def test_pre_generate_skips_terminated_employees(tenant) -> None:
    company, _oficial, ars, emp1 = _setup(tenant)
    emp2 = Employee.objects.create(company=company, termination_date=date(2026, 4, 1))
    period = _make_period(company)

    created = pre_generate_entries_for_period(period)
    assert len(created) == 1
    assert created[0].employee_id == emp1.pk


def test_pre_generate_is_idempotent(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    period = _make_period(company)
    pre_generate_entries_for_period(period)
    again = pre_generate_entries_for_period(period)
    assert len(again) == 0
    assert PayrollEntry.objects.filter(payroll_period=period).count() == 1


def test_pre_generate_picks_up_last_known_salary(tenant) -> None:
    company, _oficial, ars, emp = _setup(tenant)
    emp.last_known_salary = Decimal("999")
    emp.last_known_currency = ars
    emp.save()
    period = _make_period(company)
    created = pre_generate_entries_for_period(period)
    assert created[0].value_jornal == Decimal("999")
