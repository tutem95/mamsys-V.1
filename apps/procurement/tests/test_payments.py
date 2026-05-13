"""PurchasePayment: status automático y conversión de moneda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Rubro, Supplier
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.pricing.models import ExchangeRate, ExchangeRateType
from apps.procurement.models import Purchase, PurchasePayment


def _purchase(tenant, total, currency_code="ARS") -> Purchase:
    company = Company.objects.create(name="PASFAS SA")
    supplier = Supplier.objects.create(name="CRN", code="CRN001")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    currency = Currency.objects.get(code=currency_code)
    return Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=currency,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.TO_PAY,
        amount_without_tax=total,
        total_amount=total,
    )


def test_partial_payment_marks_paid_partial(tenant) -> None:
    p = _purchase(tenant, Decimal("1000"))
    ars = Currency.objects.get(code="ARS")
    PurchasePayment.objects.create(
        purchase=p, payment_date=date(2026, 5, 13),
        amount=Decimal("400"), currency=ars,
    )
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID_PARTIAL


def test_payment_equal_to_total_marks_paid(tenant) -> None:
    p = _purchase(tenant, Decimal("1000"))
    ars = Currency.objects.get(code="ARS")
    PurchasePayment.objects.create(
        purchase=p, payment_date=date(2026, 5, 13),
        amount=Decimal("1000"), currency=ars,
    )
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID


def test_payment_exceeding_total_still_marks_paid(tenant) -> None:
    p = _purchase(tenant, Decimal("1000"))
    ars = Currency.objects.get(code="ARS")
    PurchasePayment.objects.create(
        purchase=p, payment_date=date(2026, 5, 13),
        amount=Decimal("1200"), currency=ars,
    )
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID


def test_multiple_payments_sum_up(tenant) -> None:
    p = _purchase(tenant, Decimal("1000"))
    ars = Currency.objects.get(code="ARS")
    PurchasePayment.objects.create(purchase=p, payment_date=date(2026, 5, 13), amount=Decimal("300"), currency=ars)
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID_PARTIAL
    PurchasePayment.objects.create(purchase=p, payment_date=date(2026, 5, 14), amount=Decimal("700"), currency=ars)
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID


def test_deleting_all_payments_returns_to_to_pay(tenant) -> None:
    p = _purchase(tenant, Decimal("1000"))
    ars = Currency.objects.get(code="ARS")
    pay = PurchasePayment.objects.create(
        purchase=p, payment_date=date(2026, 5, 13),
        amount=Decimal("1000"), currency=ars,
    )
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID
    pay.delete()
    p.refresh_from_db()
    assert p.status == Purchase.Status.TO_PAY


def test_payment_in_other_currency_converts_using_default(tenant) -> None:
    """Compra en ARS, pago en USD: se convierte usando el ExchangeRateType default."""
    p = _purchase(tenant, Decimal("120000"))  # ARS
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    bna = ExchangeRateType.objects.create(
        name="BNA", currency_from=usd, currency_to=ars, is_default=True,
    )
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))

    PurchasePayment.objects.create(
        purchase=p, payment_date=date(2026, 5, 13),
        amount=Decimal("100"), currency=usd,  # 100 USD × 1200 = 120000 ARS
    )
    p.refresh_from_db()
    assert p.status == Purchase.Status.PAID
