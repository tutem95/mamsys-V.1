"""PayrollAllocation y PayrollExtraordinary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.models import ExtraordinaryConcept, Position
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.payroll.forms import PayrollAllocationFormSet
from apps.payroll.models import (
    Employee,
    EmployeePersonalData,
    PayrollAllocation,
    PayrollEntry,
    PayrollExtraordinary,
    PayrollPeriod,
)
from apps.projects.models import Project


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    oficial = Position.objects.create(name="Oficial")
    ars = Currency.objects.get(code="ARS")
    emp = Employee.objects.create(company=company, position=oficial)
    EmployeePersonalData.objects.create(employee=emp, first_name="Juan", last_name="Pérez")
    period = PayrollPeriod.objects.create(
        company=company, period_number=1, month=5, year=2026,
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 15),
        working_days=10, saturdays=2, holidays=0, total_days=12,
        hours_weekday=8, hours_saturday=7, total_hours=94,
        plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"),
    )
    entry = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("1000"), days_worked=Decimal("10"),
    )
    return company, ars, emp, period, entry


# ---------------------------------------------------------------------------
# Extraordinarios
# ---------------------------------------------------------------------------

def test_extraordinary_income_increases_net(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    bono = ExtraordinaryConcept.objects.create(name="BONO", type=ExtraordinaryConcept.Type.INCOME)
    # entry.gross = 10*1000 = 10000; net = 10000 originalmente.
    assert entry.net == Decimal("10000")
    PayrollExtraordinary.objects.create(payroll_entry=entry, concept=bono, amount=Decimal("500"))
    entry.refresh_from_db()
    # extraordinary_subtotal = +500; net = round10(10000 + 0 + 500) = 10500
    assert entry.extraordinary_subtotal == Decimal("500.00")
    assert entry.net == Decimal("10500")


def test_extraordinary_expense_decreases_net(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    adelanto = ExtraordinaryConcept.objects.create(name="Adelanto", type=ExtraordinaryConcept.Type.EXPENSE)
    PayrollExtraordinary.objects.create(payroll_entry=entry, concept=adelanto, amount=Decimal("300"))
    entry.refresh_from_db()
    assert entry.extraordinary_subtotal == Decimal("-300.00")
    assert entry.net == Decimal("9700")


def test_multiple_extraordinaries_sum_correctly(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    bono = ExtraordinaryConcept.objects.create(name="BONO", type=ExtraordinaryConcept.Type.INCOME)
    osde = ExtraordinaryConcept.objects.create(name="OSDE", type=ExtraordinaryConcept.Type.EXPENSE)
    PayrollExtraordinary.objects.create(payroll_entry=entry, concept=bono, amount=Decimal("1000"))
    PayrollExtraordinary.objects.create(payroll_entry=entry, concept=osde, amount=Decimal("200"))
    PayrollExtraordinary.objects.create(payroll_entry=entry, concept=osde, amount=Decimal("100"))
    entry.refresh_from_db()
    # +1000 - 200 - 100 = +700
    assert entry.extraordinary_subtotal == Decimal("700.00")
    assert entry.net == Decimal("10700")


def test_delete_extraordinary_recalculates_entry(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    bono = ExtraordinaryConcept.objects.create(name="BONO", type=ExtraordinaryConcept.Type.INCOME)
    x = PayrollExtraordinary.objects.create(payroll_entry=entry, concept=bono, amount=Decimal("500"))
    entry.refresh_from_db()
    assert entry.net == Decimal("10500")
    x.delete()
    entry.refresh_from_db()
    assert entry.extraordinary_subtotal == Decimal("0.00")
    assert entry.net == Decimal("10000")


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------

def test_allocation_gets_proportional_amounts_on_create(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    p = Project.objects.create(name="Casa Magdalena", company=company)
    alloc = PayrollAllocation.objects.create(payroll_entry=entry, project=p, pct=Decimal("100"))
    alloc.refresh_from_db()
    assert alloc.jornal_amount == Decimal("10000.00")
    assert alloc.net_amount == Decimal("10000.00")


def test_allocation_repartija_segun_pct(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    p1 = Project.objects.create(name="Obra A", company=company)
    p2 = Project.objects.create(name="Obra B", company=company)
    a1 = PayrollAllocation.objects.create(payroll_entry=entry, project=p1, pct=Decimal("60"))
    a2 = PayrollAllocation.objects.create(payroll_entry=entry, project=p2, pct=Decimal("40"))
    a1.refresh_from_db(); a2.refresh_from_db()
    assert a1.jornal_amount == Decimal("6000.00")
    assert a2.jornal_amount == Decimal("4000.00")
    assert a1.net_amount + a2.net_amount == Decimal("10000.00")


def test_entry_save_repartija_a_allocations_existentes(tenant) -> None:
    """Cambiar el jornal de la entry debe actualizar las allocations."""
    company, ars, emp, period, entry = _setup(tenant)
    p = Project.objects.create(name="Casa Magdalena", company=company)
    PayrollAllocation.objects.create(payroll_entry=entry, project=p, pct=Decimal("100"))
    # Subir el jornal de 1000 a 1500.
    entry.value_jornal = Decimal("1500")
    entry.save()
    alloc = PayrollAllocation.objects.get(payroll_entry=entry, project=p)
    # nuevo gross = 10*1500 = 15000
    assert alloc.jornal_amount == Decimal("15000.00")
    assert alloc.net_amount == Decimal("15000.00")


# ---------------------------------------------------------------------------
# Validación de formset de allocations: suma de pct = 100
# ---------------------------------------------------------------------------

def _formset_data(rows: list[dict]) -> dict:
    """Arma el POST data crudo para PayrollAllocationFormSet.

    El prefix default del inline formset es el related_name de la FK
    (allocations), no `payrollallocation_set`.
    """
    n = len(rows)
    data = {
        "allocations-TOTAL_FORMS": str(n),
        "allocations-INITIAL_FORMS": "0",
        "allocations-MIN_NUM_FORMS": "0",
        "allocations-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for k, v in row.items():
            data[f"allocations-{i}-{k}"] = v
    return data


def test_allocation_formset_rejects_sum_not_100(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    p1 = Project.objects.create(name="Obra A", company=company)
    p2 = Project.objects.create(name="Obra B", company=company)
    data = _formset_data([
        {"project": str(p1.pk), "pct": "60", "notes": ""},
        {"project": str(p2.pk), "pct": "30", "notes": ""},  # suma 90
    ])
    fs = PayrollAllocationFormSet(data, instance=entry)
    assert not fs.is_valid()
    assert any("100" in str(e) for e in fs.non_form_errors())


def test_allocation_formset_accepts_sum_100(tenant) -> None:
    company, ars, emp, period, entry = _setup(tenant)
    p1 = Project.objects.create(name="Obra A", company=company)
    p2 = Project.objects.create(name="Obra B", company=company)
    data = _formset_data([
        {"project": str(p1.pk), "pct": "70", "notes": ""},
        {"project": str(p2.pk), "pct": "30", "notes": ""},
    ])
    fs = PayrollAllocationFormSet(data, instance=entry)
    assert fs.is_valid()


def test_allocation_formset_accepts_empty(tenant) -> None:
    """Sin imputaciones cargadas también es OK."""
    company, ars, emp, period, entry = _setup(tenant)
    data = _formset_data([])
    fs = PayrollAllocationFormSet(data, instance=entry)
    assert fs.is_valid()
