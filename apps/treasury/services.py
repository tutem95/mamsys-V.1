"""Servicios de tesorería: saldos por cuenta, cash flow agregado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal

from django.db.models import Q, Sum

from .models import TreasuryEntry


@dataclass
class AccountBalance:
    bank_account_id: int | None
    label: str
    currency_code: str
    income: Decimal
    expense: Decimal
    balance: Decimal


def compute_account_balances(*, cutoff_date: _date | None = None, company_id: int | None = None) -> list[AccountBalance]:
    """Saldo por cuenta (sumando entries no canceladas).

    Si una entry no tiene `bank_account`, va al bucket "Efectivo".
    """
    from apps.catalog.models import BankAccount

    qs = TreasuryEntry.objects.all()
    if cutoff_date is not None:
        qs = qs.filter(date__lte=cutoff_date)
    if company_id is not None:
        qs = qs.filter(company_id=company_id)

    # Agrupar por bank_account.
    by_account: dict[int | None, dict] = {}

    for entry in qs.select_related("bank_account__bank", "bank_account__currency", "currency"):
        ba = entry.bank_account
        key = ba.pk if ba else None
        if key not in by_account:
            if ba:
                by_account[key] = {
                    "id": ba.pk,
                    "label": str(ba),
                    "currency_code": ba.currency.code,
                    "income": Decimal("0"),
                    "expense": Decimal("0"),
                }
            else:
                by_account[key] = {
                    "id": None,
                    "label": f"Efectivo ({entry.currency.code})",
                    "currency_code": entry.currency.code,
                    "income": Decimal("0"),
                    "expense": Decimal("0"),
                }
        if entry.entry_type == TreasuryEntry.EntryType.INCOME:
            by_account[key]["income"] += entry.amount
        elif entry.entry_type == TreasuryEntry.EntryType.EXPENSE:
            by_account[key]["expense"] += entry.amount
        # Transfer y currency_exchange: por simplicidad no afectan saldos
        # acá (los modelamos como 2 entries cuando hagamos el split correcto).

    rows: list[AccountBalance] = []
    for data in by_account.values():
        balance = (data["income"] - data["expense"]).quantize(Decimal("0.01"))
        rows.append(AccountBalance(
            bank_account_id=data["id"],
            label=data["label"],
            currency_code=data["currency_code"],
            income=data["income"].quantize(Decimal("0.01")),
            expense=data["expense"].quantize(Decimal("0.01")),
            balance=balance,
        ))
    rows.sort(key=lambda r: r.label)
    return rows
