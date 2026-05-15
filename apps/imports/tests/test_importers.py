"""Importadores Rubro / Subrubro / Material."""

from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import Material, Rubro, Subrubro, Unit
from apps.imports.importers import MaterialImporter, RubroImporter, SubrubroImporter


def test_rubro_importer_creates_rows(tenant) -> None:
    rows = [
        {"name": "ESTRUCTURA", "code": ""},
        {"name": "ALBAÑILERIA", "code": "ALB"},
    ]
    result = RubroImporter().run(rows, dry_run=False)
    assert result.rows_created == 2
    assert result.rows_error == 0
    assert Rubro.objects.filter(name="ESTRUCTURA").exists()
    assert Rubro.objects.get(name="ALBAÑILERIA").code == "ALB"


def test_rubro_importer_dry_run_does_not_persist(tenant) -> None:
    rows = [{"name": "DEMOLICION", "code": ""}]
    result = RubroImporter().run(rows, dry_run=True)
    assert result.rows_created == 1
    assert not Rubro.objects.filter(name="DEMOLICION").exists()


def test_rubro_importer_updates_existing(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA", code="OLD")
    rows = [{"name": "ESTRUCTURA", "code": "NEW"}]
    result = RubroImporter().run(rows, dry_run=False)
    assert result.rows_updated == 1
    assert Rubro.objects.get(name="ESTRUCTURA").code == "NEW"


def test_rubro_importer_rejects_empty_name(tenant) -> None:
    rows = [{"name": "", "code": "X"}]
    result = RubroImporter().run(rows, dry_run=False)
    assert result.rows_error == 1
    assert result.rows_created == 0


def test_subrubro_requires_existing_rubro(tenant) -> None:
    rows = [{"rubro": "INEXISTENTE", "name": "Sub", "code": ""}]
    result = SubrubroImporter().run(rows, dry_run=False)
    assert result.rows_error == 1
    assert "no existe" in result.errors[0].message.lower()


def test_subrubro_creates_under_rubro(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA")
    rows = [{"rubro": "ESTRUCTURA", "name": "HORMIGON", "code": ""}]
    result = SubrubroImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    assert Subrubro.objects.filter(name="HORMIGON").exists()


def test_material_importer_requires_existing_rubro_and_unit(tenant) -> None:
    rows = [{
        "name": "Cemento", "rubro": "NOEXISTE", "unit": "kg",
        "subrubro": "", "description": "", "last_price": "",
    }]
    result = MaterialImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_material_importer_creates_with_price(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    unit = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    rows = [{
        "name": "Cemento", "rubro": "ESTRUCTURA", "unit": "kg",
        "subrubro": "", "description": "Cemento Portland", "last_price": "1234.56",
    }]
    result = MaterialImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    mat = Material.objects.get(name="Cemento")
    assert mat.rubro == rubro
    assert mat.unit == unit
    assert mat.last_known_price == Decimal("1234.56")
    assert mat.description == "Cemento Portland"


def test_material_importer_accepts_comma_decimal(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA")
    Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    rows = [{
        "name": "Cal", "rubro": "ESTRUCTURA", "unit": "kg",
        "subrubro": "", "description": "", "last_price": "1234,56",
    }]
    result = MaterialImporter().run(rows, dry_run=False)
    assert result.rows_created == 1
    assert Material.objects.get(name="Cal").last_known_price == Decimal("1234.56")


def test_material_importer_rejects_invalid_price(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA")
    Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    rows = [{
        "name": "Cal", "rubro": "ESTRUCTURA", "unit": "kg",
        "subrubro": "", "description": "", "last_price": "no es número",
    }]
    result = MaterialImporter().run(rows, dry_run=False)
    assert result.rows_error == 1


def test_material_importer_validates_subrubro_belongs_to_rubro(tenant) -> None:
    rubro_a = Rubro.objects.create(name="ESTRUCTURA")
    rubro_b = Rubro.objects.create(name="ALBAÑILERIA")
    Subrubro.objects.create(rubro=rubro_b, name="MAMPOSTERIA")
    Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    rows = [{
        "name": "Cemento", "rubro": "ESTRUCTURA", "unit": "kg",
        "subrubro": "MAMPOSTERIA",  # pertenece a otro rubro
        "description": "", "last_price": "",
    }]
    result = MaterialImporter().run(rows, dry_run=False)
    assert result.rows_error == 1
