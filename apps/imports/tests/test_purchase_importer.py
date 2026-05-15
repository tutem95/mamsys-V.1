"""PurchaseImporter: cabecera + items con grouping."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import Material, Rubro, Subcontract, Supplier, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.imports.importers import PurchaseImporter
from apps.procurement.models import Purchase, PurchaseItem
from apps.projects.models import Project


def _setup(tenant):
    Company.objects.create(name="PASFAS SA")
    Supplier.objects.create(name="CORRALON CENTRO")
    Rubro.objects.create(name="ESTRUCTURA")
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    rubro = Rubro.objects.get(name="ESTRUCTURA")
    Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    Material.objects.create(name="Arena", rubro=rubro, unit=kg)
    Project.objects.create(name="Casa Demo", company=Company.objects.get(name="PASFAS SA"))
    return None


def test_purchase_creates_single_group_with_two_items(tenant) -> None:
    _setup(tenant)
    rows = [
        {
            "document_number": "0001-12345", "invoice_date": "2026-05-10",
            "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
            "rubro": "ESTRUCTURA", "currency": "ARS",
            "total_amount": "12100", "amount_without_tax": "10000", "iva_21": "2100",
            "purchase_type": "obra", "project": "Casa Demo",
            "item_material": "Cemento", "item_quantity": "50",
            "item_unit": "kg", "item_unit_price": "100",
        },
        {
            "document_number": "0001-12345", "invoice_date": "2026-05-10",
            "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
            "rubro": "ESTRUCTURA", "currency": "ARS",
            "total_amount": "12100",
            "purchase_type": "obra", "project": "Casa Demo",
            "item_material": "Arena", "item_quantity": "100",
            "item_unit": "kg", "item_unit_price": "50",
        },
    ]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_total == 1  # un grupo
    assert result.rows_created == 1
    assert result.rows_error == 0

    p = Purchase.objects.get(document_number="0001-12345")
    assert p.items.count() == 2
    assert p.total_amount == Decimal("12100")
    assert p.amount_without_tax == Decimal("10000")
    assert p.iva_21 == Decimal("2100")


def test_purchase_dry_run_does_not_persist(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-99999", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "1000",
        "purchase_type": "admin",
    }]
    result = PurchaseImporter().run(rows, dry_run=True)
    assert result.rows_created == 1
    assert not Purchase.objects.filter(document_number="0001-99999").exists()


def test_purchase_reimport_replaces_items(tenant) -> None:
    _setup(tenant)
    rows_v1 = [{
        "document_number": "0001-77777", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "5000",
        "purchase_type": "obra", "project": "Casa Demo",
        "item_material": "Cemento", "item_quantity": "50",
        "item_unit": "kg", "item_unit_price": "100",
    }]
    PurchaseImporter().run(rows_v1, dry_run=False)
    assert PurchaseItem.objects.filter(material__name="Cemento").count() == 1

    rows_v2 = [{
        "document_number": "0001-77777", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "5000",
        "purchase_type": "obra", "project": "Casa Demo",
        "item_material": "Arena", "item_quantity": "100",
        "item_unit": "kg", "item_unit_price": "50",
    }]
    result = PurchaseImporter().run(rows_v2, dry_run=False)
    assert result.rows_updated == 1
    p = Purchase.objects.get(document_number="0001-77777")
    assert p.items.count() == 1
    assert p.items.first().material.name == "Arena"


def test_purchase_obra_without_project_fails(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-NOPROJ", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "1000", "purchase_type": "obra",
    }]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_purchase_admin_without_project_ok(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-ADMIN", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "1000", "purchase_type": "admin",
    }]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_created == 1


def test_purchase_rejects_unknown_supplier(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-X", "invoice_date": "2026-05-10",
        "supplier": "INEXISTENTE", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS", "total_amount": "1000",
        "purchase_type": "admin",
    }]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_purchase_item_with_missing_data_fails(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-BADITEM", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS", "total_amount": "1000",
        "purchase_type": "admin",
        "item_material": "Cemento",
        # falta quantity y unit_price
    }]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_error == 1
    assert not Purchase.objects.filter(document_number="0001-BADITEM").exists()


def test_purchase_unit_defaults_to_material_unit(tenant) -> None:
    _setup(tenant)
    rows = [{
        "document_number": "0001-DEFUNIT", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS", "total_amount": "5000",
        "purchase_type": "admin",
        "item_material": "Cemento", "item_quantity": "50", "item_unit_price": "100",
        # item_unit vacío → toma del material
    }]
    result = PurchaseImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    item = Purchase.objects.get(document_number="0001-DEFUNIT").items.first()
    assert item.unit.symbol == "kg"


def test_purchase_signal_creates_price(tenant) -> None:
    """Al confirmar (status=to_pay) el signal de procurement debe crear un Price."""
    from django.contrib.contenttypes.models import ContentType
    from apps.pricing.models import Price

    _setup(tenant)
    rows = [{
        "document_number": "0001-SIGNAL", "invoice_date": "2026-05-10",
        "supplier": "CORRALON CENTRO", "company": "PASFAS SA",
        "rubro": "ESTRUCTURA", "currency": "ARS",
        "total_amount": "5000", "status": "to_pay",
        "purchase_type": "obra", "project": "Casa Demo",
        "item_material": "Cemento", "item_quantity": "50",
        "item_unit": "kg", "item_unit_price": "100",
    }]
    PurchaseImporter().run(rows, dry_run=False)
    ct = ContentType.objects.get_for_model(Material)
    cemento = Material.objects.get(name="Cemento")
    prices = Price.objects.filter(content_type=ct, object_id=cemento.pk)
    assert prices.count() >= 1
    assert prices.first().amount == Decimal("100")
