"""Servicios de payroll.

SocialChargesProrateService implementa la regla del SPEC §9.4:

  on_social_charges_payment_created(payment):
      entries = PayrollEntry of company in same month (ambas quincenas)
      total_gross = Sum(entries.gross)
      for entry:
          pct_employee = entry.gross / total_gross
          cs_for_employee = payment.total_amount * pct_employee
          for allocation in entry.allocations:
              allocation.social_charges_amount = cs_for_employee * (allocation.pct / 100)
              allocation.total_amount = net + cs
              allocation.social_charges_status = 'real'
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SocialChargesPayment


@dataclass
class ProrateLine:
    employee_id: int
    employee_name: str
    gross: Decimal
    pct_of_total: Decimal
    cs_assigned: Decimal
    allocations_count: int


@dataclass
class ProrateResult:
    payment: "SocialChargesPayment"
    total_gross: Decimal
    lines: list[ProrateLine]
    allocations_updated: int
    entries_without_allocations: int


class SocialChargesProrateService:
    """Prorratea un SocialChargesPayment a las allocations de las entries del mes."""

    @classmethod
    def prorate(cls, payment: "SocialChargesPayment") -> ProrateResult:
        from django.db.models import Sum

        from .models import PayrollAllocation, PayrollEntry

        entries = (
            PayrollEntry.objects
            .filter(
                payroll_period__company=payment.company,
                payroll_period__year=payment.period_year,
                payroll_period__month=payment.period_month,
            )
            .select_related("employee__personal_data")
        )

        total_gross = entries.aggregate(t=Sum("gross"))["t"] or Decimal("0")
        if total_gross == 0:
            return ProrateResult(
                payment=payment,
                total_gross=total_gross,
                lines=[],
                allocations_updated=0,
                entries_without_allocations=entries.count(),
            )

        lines: list[ProrateLine] = []
        allocations_updated = 0
        entries_without = 0

        for entry in entries:
            entry_gross = entry.gross or Decimal("0")
            if entry_gross <= 0:
                continue
            pct_employee = entry_gross / total_gross
            cs_for_employee = (payment.total_amount * pct_employee).quantize(Decimal("0.01"))

            allocs = list(entry.allocations.all())
            if not allocs:
                entries_without += 1
            for alloc in allocs:
                alloc_pct = (alloc.pct or Decimal("0")) / Decimal("100")
                alloc.social_charges_amount = (cs_for_employee * alloc_pct).quantize(Decimal("0.01"))
                alloc.total_amount = (alloc.net_amount + alloc.social_charges_amount).quantize(Decimal("0.01"))
                alloc.social_charges_status = "real"
                PayrollAllocation.objects.filter(pk=alloc.pk).update(
                    social_charges_amount=alloc.social_charges_amount,
                    total_amount=alloc.total_amount,
                    social_charges_status=alloc.social_charges_status,
                )
                allocations_updated += 1

            lines.append(ProrateLine(
                employee_id=entry.employee_id,
                employee_name=entry.employee.full_name,
                gross=entry_gross,
                pct_of_total=(pct_employee * Decimal("100")).quantize(Decimal("0.01")),
                cs_assigned=cs_for_employee,
                allocations_count=len(allocs),
            ))

        return ProrateResult(
            payment=payment,
            total_gross=total_gross,
            lines=lines,
            allocations_updated=allocations_updated,
            entries_without_allocations=entries_without,
        )
