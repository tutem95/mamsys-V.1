"""TaskCostCalculator: prueba el resolver recursivo con precios reales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import Material, Rubro, Unit
from apps.currencies.models import Currency
from apps.pricing.models import Price
from apps.task_master.models import Mix, MixComponent, Task, TaskComponent
from apps.task_master.services import TaskCostCalculator


def _seed_material_price(material, amount, currency_code="ARS"):
    ars = Currency.objects.get(code=currency_code)
    ct = ContentType.objects.get_for_model(Material)
    Price.objects.create(
        content_type=ct, object_id=material.pk,
        amount=Decimal(amount), currency=ars,
        effective_date=date(2026, 5, 1),
        source=Price.Source.MANUAL, is_reference=True,
    )


def test_calculator_simple_task_with_material(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m3 = Unit.objects.create(name="m3", symbol="m3", category=Unit.Category.VOLUME)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    _seed_material_price(cemento, "100")  # 100 ARS/kg

    t = Task.objects.create(name="Hormigón H21", rubro=rubro, output_unit=m3)
    TaskComponent.objects.create(
        task=t, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento, quantity_per_unit=Decimal("300"), input_unit=kg,
    )

    result = TaskCostCalculator.calculate(t, date=date(2026, 5, 13))
    assert result.total == Decimal("30000.0000")
    assert len(result.components) == 1
    assert result.components[0].source_type == "material"
    assert result.total_materials == Decimal("30000.0000")
    assert result.total_labor == Decimal("0.0000")


def test_calculator_falls_back_to_last_known_price_when_no_Price(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m3 = Unit.objects.create(name="m3", symbol="m3", category=Unit.Category.VOLUME)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    arena = Material.objects.create(
        name="Arena", rubro=rubro, unit=kg, last_known_price=Decimal("50"),
    )
    t = Task.objects.create(name="Mortero", rubro=rubro, output_unit=m3)
    TaskComponent.objects.create(
        task=t, source_type=TaskComponent.SourceType.MATERIAL,
        material=arena, quantity_per_unit=Decimal("200"), input_unit=kg,
    )

    result = TaskCostCalculator.calculate(t, date=date(2026, 5, 13))
    # 200 × 50 (last_known_price) = 10000
    assert result.total == Decimal("10000.0000")


def test_calculator_mix_recursive(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m3 = Unit.objects.create(name="m3", symbol="m3", category=Unit.Category.VOLUME)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    _seed_material_price(cemento, "100")

    # Mezcla "Mortero" = 200 kg cemento por m3.
    mortero = Mix.objects.create(name="Mortero", output_unit=m3)
    MixComponent.objects.create(
        mix=mortero, material=cemento,
        quantity_per_unit=Decimal("200"), input_unit=kg,
    )

    # Tarea "Revoque" que usa 0.05 m3 de mortero por m2.
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    revoque = Task.objects.create(name="Revoque grueso", rubro=rubro, output_unit=m2)
    TaskComponent.objects.create(
        task=revoque, source_type=TaskComponent.SourceType.SUB_MIX,
        sub_mix=mortero, quantity_per_unit=Decimal("0.05"), input_unit=m3,
    )

    result = TaskCostCalculator.calculate(revoque)
    # Mortero por m3 = 200 × 100 = 20000. Revoque por m2 = 0.05 × 20000 = 1000.
    assert result.total == Decimal("1000.0000")
    # Sub-breakdown disponible
    assert mortero.pk in result.sub_breakdowns
    assert result.sub_breakdowns[mortero.pk].total == Decimal("20000.0000")


def test_calculator_task_with_subtask_recursive(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    _seed_material_price(cemento, "100")

    base = Task.objects.create(name="Base", rubro=rubro, output_unit=m2)
    TaskComponent.objects.create(
        task=base, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento, quantity_per_unit=Decimal("10"), input_unit=kg,
    )
    # base por m2 = 10 × 100 = 1000.

    parent = Task.objects.create(name="Parent", rubro=rubro, output_unit=m2)
    TaskComponent.objects.create(
        task=parent, source_type=TaskComponent.SourceType.SUB_TASK,
        sub_task=base, quantity_per_unit=Decimal("2"), input_unit=m2,
    )
    # parent por m2 = 2 × 1000 = 2000.

    result = TaskCostCalculator.calculate(parent)
    assert result.total == Decimal("2000.0000")
    assert base.pk in result.sub_breakdowns
