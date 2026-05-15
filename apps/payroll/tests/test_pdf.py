"""PDF de talonarios: smoke test del rendering del template."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.template.loader import render_to_string


def test_talonarios_template_renders(tenant) -> None:
    from apps.companies.models import Company
    from apps.currencies.models import Currency
    from apps.payroll.models import (
        Employee,
        EmployeePersonalData,
        PayrollEntry,
        PayrollPeriod,
    )

    company = Company.objects.create(name="PASFAS SA")
    period = PayrollPeriod.objects.create(
        company=company, period_number=1, year=2026, month=5,
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 15),
        plus_overtime_pct=Decimal("12"), plus_presentismo_pct=Decimal("2.30"),
    )
    emp = Employee.objects.create(company=company, internal_id="EMP-001")
    EmployeePersonalData.objects.create(employee=emp, first_name="Juan", last_name="Pérez")
    ars = Currency.objects.get(code="ARS")
    entry = PayrollEntry.objects.create(
        payroll_period=period, employee=emp, currency=ars,
        value_jornal=Decimal("25000"), days_worked=Decimal("12"),
        bank_amount=Decimal("200000"),
    )
    # entry.save() ya disparó recalculate().

    entries = PayrollPeriod.objects.get(pk=period.pk).entries.all()
    html = render_to_string("payroll/pdf/talonarios.html", {
        "period": period,
        "entries": entries,
        "today": date(2026, 5, 20),
    })

    assert "PASFAS SA" in html
    assert "Juan Pérez" in html or "Pérez" in html
    assert "Recibo operativo" in html
    assert "Neto a cobrar" in html
    assert "25000" in html or "25,000" in html or "25000.00" in html
