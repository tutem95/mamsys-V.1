"""Signal: PurchaseItem confirmado popula pricing.Price y Material.last_known_price."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import Material, Rubro, Supplier, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.pricing.models import Price
from apps.procurement.models import Purchase, PurchaseItem


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    supplier = Supplier.objects.create(name="CORRALON CENTRO", code="CRN001")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    unit = Unit.objects.create(name="Kilogramo", symbol="kg", category=Unit.Category.WEIGHT)
    material = Material.objects.create(name="Cemento", rubro=rubro, unit=unit)
    ars = Currency.objects.get(code="ARS")
    return company, supplier, rubro, unit, material, ars


def test_signal_does_not_fire_for_draft_purchase(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.DRAFT,
        amount_without_tax=Decimal("1000.00"),
    )
    PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("10"), unit=unit, unit_price=Decimal("100"),
    )
    assert Price.objects.count() == 0


def test_signal_creates_price_for_confirmed_purchase(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.TO_PAY,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("10"), unit=unit, unit_price=Decimal("100"),
    )
    ct = ContentType.objects.get_for_model(Material)
    price = Price.objects.get(source_purchase_item_id=item.pk)
    assert price.amount == Decimal("100")
    assert price.currency == ars
    assert price.effective_date == date(2026, 5, 13)
    assert price.content_type == ct
    assert price.object_id == material.pk


def test_signal_updates_material_last_known_price(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.TO_PAY,
        amount_without_tax=Decimal("1000.00"),
    )
    PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("10"), unit=unit, unit_price=Decimal("123.4500"),
    )
    material.refresh_from_db()
    assert material.last_known_price == Decimal("123.4500")


def test_signal_upserts_price_on_item_edit(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.TO_PAY,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("10"), unit=unit, unit_price=Decimal("100"),
    )
    item.unit_price = Decimal("150")
    item.save()
    # No se crean Prices duplicados; el existente se actualiza.
    assert Price.objects.filter(source_purchase_item_id=item.pk).count() == 1
    assert Price.objects.get(source_purchase_item_id=item.pk).amount == Decimal("150")


def test_status_transition_draft_to_to_pay_alimenta_prices_existentes(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        status=Purchase.Status.DRAFT,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("10"), unit=unit, unit_price=Decimal("100"),
    )
    # Estaba draft: no debería haber Price todavía.
    assert Price.objects.filter(source_purchase_item_id=item.pk).count() == 0

    # Al pasar a TO_PAY el signal de Purchase debe alimentar el Price.
    p.status = Purchase.Status.TO_PAY
    p.save()
    assert Price.objects.filter(source_purchase_item_id=item.pk).count() == 1
