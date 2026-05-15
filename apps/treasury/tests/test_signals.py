"""Signals que crean TreasuryEntry desde PurchasePayment y SocialChargesPayment."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Rubro, Supplier
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.payroll.models import SocialChargesPayment
from apps.procurement.models import Purchase, PurchasePayment
from apps.projects.models import Project
from apps.treasury.models import TreasuryEntry


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    supplier = Supplier.objects.create(name="CORRALON")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    ars = Currency.objects.get(code="ARS")
    project = Project.objects.create(name="Casa Demo", company=company)
    return company, supplier, rubro, ars, project


def test_purchase_payment_creates_treasury_entry(tenant) -> None:
    company, supplier, rubro, ars, project = _setup(tenant)
    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        document_number="0001-12345",
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        total_amount=Decimal("10000"),
    )
    payment = PurchasePayment.objects.create(
        purchase=purchase,
        payment_date=date(2026, 5, 12),
        amount=Decimal("5000"),
        currency=ars,
    )
    entry = TreasuryEntry.objects.get(source_purchase_payment=payment)
    assert entry.entry_type == TreasuryEntry.EntryType.EXPENSE
    assert entry.category == TreasuryEntry.Category.SUPPLIER_PAYMENT
    assert entry.amount == Decimal("5000")
    assert entry.currency == ars
    assert entry.company == company
    assert entry.project == project
    assert "CORRALON" in entry.description


def test_purchase_payment_update_is_idempotent(tenant) -> None:
    company, supplier, rubro, ars, project = _setup(tenant)
    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        total_amount=Decimal("10000"),
    )
    payment = PurchasePayment.objects.create(
        purchase=purchase, payment_date=date(2026, 5, 12),
        amount=Decimal("5000"), currency=ars,
    )
    payment.amount = Decimal("7000")
    payment.save()
    entries = TreasuryEntry.objects.filter(source_purchase_payment=payment)
    assert entries.count() == 1
    assert entries.first().amount == Decimal("7000")


def test_purchase_payment_delete_removes_treasury_entry(tenant) -> None:
    company, supplier, rubro, ars, project = _setup(tenant)
    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        total_amount=Decimal("10000"),
    )
    payment = PurchasePayment.objects.create(
        purchase=purchase, payment_date=date(2026, 5, 12),
        amount=Decimal("5000"), currency=ars,
    )
    payment_pk = payment.pk
    payment.delete()
    assert not TreasuryEntry.objects.filter(source_purchase_payment_id=payment_pk).exists()


def test_social_charges_payment_creates_treasury_entry(tenant) -> None:
    company, supplier, rubro, ars, project = _setup(tenant)
    cs = SocialChargesPayment.objects.create(
        company=company,
        period_month=5, period_year=2026,
        total_amount=Decimal("80000"),
        currency=ars,
        payment_date=date(2026, 5, 15),
        reference="REF-001",
    )
    entry = TreasuryEntry.objects.get(source_social_charges_payment=cs)
    assert entry.entry_type == TreasuryEntry.EntryType.EXPENSE
    assert entry.category == TreasuryEntry.Category.SOCIAL_CHARGES_PAYMENT
    assert entry.amount == Decimal("80000")
    assert entry.company == company
    assert "05/2026" in entry.description
    assert "REF-001" in entry.description


def test_social_charges_payment_delete_removes_entry(tenant) -> None:
    company, _, _, ars, _ = _setup(tenant)
    cs = SocialChargesPayment.objects.create(
        company=company, period_month=5, period_year=2026,
        total_amount=Decimal("1000"), currency=ars, payment_date=date(2026, 5, 15),
    )
    pk = cs.pk
    cs.delete()
    assert not TreasuryEntry.objects.filter(source_social_charges_payment_id=pk).exists()


def test_balances_aggregate_correctly(tenant) -> None:
    from apps.catalog.models import Bank, BankAccount
    from apps.treasury.services import compute_account_balances

    company, _, _, ars, _ = _setup(tenant)
    bank = Bank.objects.create(name="Galicia")
    account = BankAccount.objects.create(
        bank=bank, company=company, currency=ars,
        name="Cuenta Op", account_number="123",
    )

    TreasuryEntry.objects.create(
        entry_type=TreasuryEntry.EntryType.INCOME,
        category=TreasuryEntry.Category.CLIENT_PAYMENT,
        date=date(2026, 5, 10),
        company=company, bank_account=account,
        amount=Decimal("100000"), currency=ars,
    )
    TreasuryEntry.objects.create(
        entry_type=TreasuryEntry.EntryType.EXPENSE,
        category=TreasuryEntry.Category.TAXES,
        date=date(2026, 5, 11),
        company=company, bank_account=account,
        amount=Decimal("15000"), currency=ars,
    )
    # Efectivo (sin bank_account).
    TreasuryEntry.objects.create(
        entry_type=TreasuryEntry.EntryType.EXPENSE,
        category=TreasuryEntry.Category.ADMIN,
        date=date(2026, 5, 12),
        company=company, amount=Decimal("3000"), currency=ars,
    )

    rows = compute_account_balances()
    by_id = {r.bank_account_id: r for r in rows}
    assert by_id[account.pk].income == Decimal("100000.00")
    assert by_id[account.pk].expense == Decimal("15000.00")
    assert by_id[account.pk].balance == Decimal("85000.00")
    assert by_id[None].expense == Decimal("3000.00")
    assert by_id[None].balance == Decimal("-3000.00")
