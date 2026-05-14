"""Modelos Mix / Task con validaciones de ciclo y consistencia de source_type."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import Material, Position, Rubro, Subcontract, Unit
from apps.task_master.models import Mix, MixComponent, Task, TaskComponent


def _setup(tenant):
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    unit_m3 = Unit.objects.create(name="m3", symbol="m3", category=Unit.Category.VOLUME)
    unit_kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    unit_uni = Unit.objects.create(name="uni", symbol="UNI", category=Unit.Category.OTHER)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=unit_kg)
    arena = Material.objects.create(name="Arena", rubro=rubro, unit=unit_kg)
    sc = Subcontract.objects.create(name="Estudio Suelo", unit=unit_uni)
    position = Position.objects.create(name="Oficial")
    return rubro, unit_m3, unit_kg, unit_uni, cemento, arena, sc, position


def test_mix_str(tenant) -> None:
    _, unit_m3, *_ = _setup(tenant)
    m = Mix.objects.create(name="Concreto H21", output_unit=unit_m3)
    assert str(m) == "Concreto H21"


def test_mix_unique_name(tenant) -> None:
    _, unit_m3, *_ = _setup(tenant)
    Mix.objects.create(name="Concreto H21", output_unit=unit_m3)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Mix.objects.create(name="Concreto H21", output_unit=unit_m3)


def test_mix_component_requires_one_target(tenant) -> None:
    _, unit_m3, unit_kg, _, cemento, *_ = _setup(tenant)
    m = Mix.objects.create(name="Concreto", output_unit=unit_m3)
    comp = MixComponent(mix=m, quantity_per_unit=Decimal("300"), input_unit=unit_kg)
    with pytest.raises(ValidationError):
        comp.full_clean()


def test_mix_component_rejects_both(tenant) -> None:
    _, unit_m3, unit_kg, _, cemento, *_ = _setup(tenant)
    other_mix = Mix.objects.create(name="Mortero", output_unit=unit_m3)
    m = Mix.objects.create(name="Concreto", output_unit=unit_m3)
    comp = MixComponent(
        mix=m, material=cemento, sub_mix=other_mix,
        quantity_per_unit=Decimal("1"), input_unit=unit_kg,
    )
    with pytest.raises(ValidationError):
        comp.full_clean()


def test_mix_cannot_reference_itself_as_sub_mix(tenant) -> None:
    _, unit_m3, unit_kg, *_ = _setup(tenant)
    m = Mix.objects.create(name="Concreto", output_unit=unit_m3)
    comp = MixComponent(
        mix=m, sub_mix=m,
        quantity_per_unit=Decimal("1"), input_unit=unit_kg,
    )
    with pytest.raises(ValidationError):
        comp.full_clean()


def test_mix_cycle_two_hops_rejected(tenant) -> None:
    _, unit_m3, unit_kg, *_ = _setup(tenant)
    a = Mix.objects.create(name="A", output_unit=unit_m3)
    b = Mix.objects.create(name="B", output_unit=unit_m3)
    # B usa a A.
    MixComponent.objects.create(
        mix=b, sub_mix=a,
        quantity_per_unit=Decimal("1"), input_unit=unit_m3,
    )
    # Querer poner A usando B genera ciclo (A→B→A).
    cyclic = MixComponent(
        mix=a, sub_mix=b,
        quantity_per_unit=Decimal("1"), input_unit=unit_m3,
    )
    with pytest.raises(ValidationError):
        cyclic.full_clean()


def test_task_component_material_source_requires_material(tenant) -> None:
    rubro, unit_m3, unit_kg, unit_uni, cemento, arena, sc, position = _setup(tenant)
    t = Task.objects.create(name="Tarea X", rubro=rubro, output_unit=unit_m3)
    comp = TaskComponent(
        task=t, source_type=TaskComponent.SourceType.MATERIAL,
        # falta material
        quantity_per_unit=Decimal("1"), input_unit=unit_kg,
    )
    with pytest.raises(ValidationError):
        comp.full_clean()


def test_task_component_material_source_auto_sets_classification(tenant) -> None:
    rubro, unit_m3, unit_kg, unit_uni, cemento, arena, sc, position = _setup(tenant)
    t = Task.objects.create(name="Tarea Y", rubro=rubro, output_unit=unit_m3)
    comp = TaskComponent(
        task=t, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento,
        quantity_per_unit=Decimal("1"), input_unit=unit_kg,
    )
    comp.full_clean()
    assert comp.classification == TaskComponent.Classification.MATERIALS


def test_task_component_labor_source_sets_labor_classification(tenant) -> None:
    rubro, unit_m3, *_, position = _setup(tenant)
    t = Task.objects.create(name="Tarea Z", rubro=rubro, output_unit=unit_m3)
    comp = TaskComponent(
        task=t, source_type=TaskComponent.SourceType.LABOR,
        position=position,
        quantity_per_unit=Decimal("1"), input_unit=unit_m3,
    )
    comp.full_clean()
    assert comp.classification == TaskComponent.Classification.LABOR


def test_task_component_extra_fk_rejected(tenant) -> None:
    rubro, unit_m3, unit_kg, _, cemento, _, _, position = _setup(tenant)
    t = Task.objects.create(name="Tarea W", rubro=rubro, output_unit=unit_m3)
    comp = TaskComponent(
        task=t, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento, position=position,  # de más
        quantity_per_unit=Decimal("1"), input_unit=unit_kg,
    )
    with pytest.raises(ValidationError):
        comp.full_clean()


def test_task_cycle_via_sub_task_rejected(tenant) -> None:
    rubro, unit_m3, *_ = _setup(tenant)
    a = Task.objects.create(name="A", rubro=rubro, output_unit=unit_m3)
    b = Task.objects.create(name="B", rubro=rubro, output_unit=unit_m3)
    TaskComponent.objects.create(
        task=b, source_type=TaskComponent.SourceType.SUB_TASK, sub_task=a,
        quantity_per_unit=Decimal("1"), input_unit=unit_m3,
    )
    cyclic = TaskComponent(
        task=a, source_type=TaskComponent.SourceType.SUB_TASK, sub_task=b,
        quantity_per_unit=Decimal("1"), input_unit=unit_m3,
    )
    with pytest.raises(ValidationError):
        cyclic.full_clean()
