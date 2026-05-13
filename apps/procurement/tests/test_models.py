from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Material, Rubro, Subcontract, Supplier, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.procurement.models import Purchase, PurchaseItem


def _setup_basics(tenant):
    company = Company.objects.create(name="PASFAS SA")
    supplier = Supplier.objects.create(name="CORRALON CENTRO", code="CRN001")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    unit = Unit.objects.create(name="Kilogramo", symbol="kg", category=Unit.Category.WEIGHT)
    material = Material.objects.create(name="Cemento", rubro=rubro, unit=unit)
    ars = Currency.objects.get(code="ARS")
    return company, supplier, rubro, unit, material, ars


def test_purchase_auto_total_when_zero(tenant) -> None:
    company, supplier, rubro, _u, _m, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        amount_without_tax=Decimal("1000.00"),
        iva_21=Decimal("210.00"),
        perc_iibb=Decimal("30.00"),
    )
    # total_amount no se cargó: el save lo arma.
    assert p.total_amount == Decimal("1240.00")


def test_purchase_keeps_total_if_provided(tenant) -> None:
    company, supplier, rubro, _u, _m, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        amount_without_tax=Decimal("1000.00"),
        total_amount=Decimal("1250.00"),  # explícito y distinto de la suma
    )
    assert p.total_amount == Decimal("1250.00")


def test_purchase_obra_requires_project(tenant) -> None:
    company, supplier, rubro, _u, _m, ars = _setup_basics(tenant)
    p = Purchase(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
    )
    with pytest.raises(ValidationError):
        p.full_clean()


def test_purchase_item_total_is_computed(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("5"), unit=unit, unit_price=Decimal("100.50"),
    )
    assert item.total == Decimal("502.50")


def test_purchase_item_flags_is_itemized(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        amount_without_tax=Decimal("1000.00"),
    )
    assert p.is_itemized is False
    PurchaseItem.objects.create(
        purchase=p, material=material,
        quantity=Decimal("1"), unit=unit, unit_price=Decimal("100"),
    )
    p.refresh_from_db()
    assert p.is_itemized is True


def test_item_rejects_both_material_and_subcontract(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup_basics(tenant)
    sc = Subcontract.objects.create(name="Estudio de Suelo", unit=unit)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem(
        purchase=p, material=material, subcontract=sc,
        quantity=Decimal("1"), unit=unit, unit_price=Decimal("100"),
    )
    with pytest.raises(ValidationError):
        item.full_clean()


def test_item_rejects_neither_material_nor_subcontract(tenant) -> None:
    company, supplier, rubro, unit, _m, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        amount_without_tax=Decimal("1000.00"),
    )
    item = PurchaseItem(
        purchase=p,
        quantity=Decimal("1"), unit=unit, unit_price=Decimal("100"),
    )
    with pytest.raises(ValidationError):
        item.full_clean()


def test_item_kind_must_match_purchase_subcontract_flag(tenant) -> None:
    company, supplier, rubro, unit, material, ars = _setup_basics(tenant)
    p = Purchase.objects.create(
        invoice_date=date(2026, 5, 13),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.ADMIN,
        is_subcontract=True,
        amount_without_tax=Decimal("1000.00"),
    )
    # La compra es subcontrato pero le pasamos un material → rechazar.
    item = PurchaseItem(
        purchase=p, material=material,
        quantity=Decimal("1"), unit=unit, unit_price=Decimal("100"),
    )
    with pytest.raises(ValidationError):
        item.full_clean()
