"""SocialChargesPayment + prorrateo a allocations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Position
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.payroll.models import (
    Employee,
    EmployeePersonalData,
    PayrollAllocation,
    PayrollEntry,
    PayrollPeriod,
    SocialChargesPayment,
)
from apps.payroll.services import SocialChargesProrateService
from apps.projects.models import Project


def _setup_company_with_entries(tenant, gross_amounts: list[Decimal]):
    """Crea sociedad con N empleados, una quincena y entries con los gross dados."""
    company = Company.objects.create(name="PASFAS SA")
    oficial = Position.objects.create(name="Oficial")
    ars = Currency.objects.get(code="ARS")

    period = PayrollPeriod.objects.create(
        company=company, period_number=1, month=5, year=2026,
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 15),
        working_days=10, saturdays=2, holidays=0, total_days=10,
        hours_weekday=8, hours_saturday=7, total_hours=94,
        plus_overtime_pct=Decimal("0"), plus_presentismo_pct=Decimal("0"),
    )

    entries = []
    for i, gross_target in enumerate(gross_amounts):
        emp = Employee.objects.create(company=company, position=oficial)
        EmployeePersonalData.objects.create(
            employee=emp, first_name=f"Emp{i}", last_name="X",
        )
        # gross = days * jornal = 10 * jornal → jornal = gross/10
        entry = PayrollEntry.objects.create(
            payroll_period=period, employee=emp, currency=ars,
            value_jornal=gross_target / Decimal("10"), days_worked=Decimal("10"),
        )
        assert entry.gross == gross_target.quantize(Decimal("0.01"))
        entries.append(entry)
    return company, ars, period, entries


def _make_payment(company, total, year=2026, month=5):
    ars = Currency.objects.get(code="ARS")
    return SocialChargesPayment.objects.create(
        company=company, period_year=year, period_month=month,
        total_amount=total, currency=ars,
        payment_date=date(year, month, 20), reference=f"CS-{year}-{month}",
    )


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------

def test_prorate_distributes_pro_rata_by_gross(tenant) -> None:
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("3000"), Decimal("7000")],
    )
    payment = _make_payment(company, Decimal("1000"))

    result = SocialChargesProrateService.prorate(payment)
    assert result.total_gross == Decimal("10000")
    # Emp con 3000 brutos: 30% → 300. Otro: 70% → 700.
    cs_by_emp = {line.employee_id: line.cs_assigned for line in result.lines}
    assert cs_by_emp[entries[0].employee_id] == Decimal("300.00")
    assert cs_by_emp[entries[1].employee_id] == Decimal("700.00")


def test_prorate_assigns_cs_to_allocations(tenant) -> None:
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("10000")],
    )
    entry = entries[0]
    p1 = Project.objects.create(name="Obra A", company=company)
    p2 = Project.objects.create(name="Obra B", company=company)
    PayrollAllocation.objects.create(payroll_entry=entry, project=p1, pct=Decimal("60"))
    PayrollAllocation.objects.create(payroll_entry=entry, project=p2, pct=Decimal("40"))

    payment = _make_payment(company, Decimal("1000"))
    SocialChargesProrateService.prorate(payment)

    a1 = PayrollAllocation.objects.get(payroll_entry=entry, project=p1)
    a2 = PayrollAllocation.objects.get(payroll_entry=entry, project=p2)
    # CS total del empleado = 1000 (es el único). Reparto 60/40.
    assert a1.social_charges_amount == Decimal("600.00")
    assert a2.social_charges_amount == Decimal("400.00")
    assert a1.social_charges_status == PayrollAllocation.CSStatus.REAL
    assert a2.social_charges_status == PayrollAllocation.CSStatus.REAL


def test_prorate_updates_total_amount(tenant) -> None:
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("10000")],
    )
    entry = entries[0]
    p = Project.objects.create(name="Obra A", company=company)
    PayrollAllocation.objects.create(payroll_entry=entry, project=p, pct=Decimal("100"))

    payment = _make_payment(company, Decimal("4000"))
    SocialChargesProrateService.prorate(payment)

    alloc = PayrollAllocation.objects.get(payroll_entry=entry, project=p)
    # net_amount = 10000 (100% del net) + cs = 4000 → total = 14000
    assert alloc.net_amount == Decimal("10000.00")
    assert alloc.social_charges_amount == Decimal("4000.00")
    assert alloc.total_amount == Decimal("14000.00")


def test_prorate_signal_runs_on_save(tenant) -> None:
    """No hay que llamar el service explícitamente — el signal lo dispara."""
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("10000")],
    )
    entry = entries[0]
    p = Project.objects.create(name="Obra A", company=company)
    PayrollAllocation.objects.create(payroll_entry=entry, project=p, pct=Decimal("100"))

    # Solo crear el payment dispara el prorrateo.
    _make_payment(company, Decimal("2500"))

    alloc = PayrollAllocation.objects.get(payroll_entry=entry, project=p)
    assert alloc.social_charges_amount == Decimal("2500.00")


def test_prorate_counts_entries_without_allocations(tenant) -> None:
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("5000"), Decimal("5000")],
    )
    # Solo el primero tiene allocation; el segundo no.
    p = Project.objects.create(name="Obra A", company=company)
    PayrollAllocation.objects.create(payroll_entry=entries[0], project=p, pct=Decimal("100"))

    payment = _make_payment(company, Decimal("1000"))
    result = SocialChargesProrateService.prorate(payment)
    assert result.entries_without_allocations == 1


def test_prorate_with_zero_total_gross_returns_empty(tenant) -> None:
    company = Company.objects.create(name="VACIA SA")
    # No hay quincenas/entries
    payment = _make_payment(company, Decimal("500"))
    result = SocialChargesProrateService.prorate(payment)
    assert result.total_gross == Decimal("0")
    assert result.lines == []
    assert result.allocations_updated == 0


def test_resaving_payment_with_new_amount_updates_allocations(tenant) -> None:
    """Editar el monto del pago re-prorratea (idempotente)."""
    company, ars, period, entries = _setup_company_with_entries(
        tenant, [Decimal("10000")],
    )
    entry = entries[0]
    p = Project.objects.create(name="Obra A", company=company)
    PayrollAllocation.objects.create(payroll_entry=entry, project=p, pct=Decimal("100"))

    payment = _make_payment(company, Decimal("1000"))
    alloc = PayrollAllocation.objects.get(payroll_entry=entry, project=p)
    assert alloc.social_charges_amount == Decimal("1000.00")

    payment.total_amount = Decimal("3000")
    payment.save()
    alloc.refresh_from_db()
    assert alloc.social_charges_amount == Decimal("3000.00")
