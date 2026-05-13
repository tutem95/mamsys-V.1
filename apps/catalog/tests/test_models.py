from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import (
    BusinessComponent,
    ExtraordinaryConcept,
    Material,
    Rubro,
    Subcontract,
    Subrubro,
    Supplier,
    Unit,
)


def test_rubro_name_is_unique(tenant) -> None:
    Rubro.objects.create(name="ESTRUCTURA")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Rubro.objects.create(name="ESTRUCTURA")


def test_subrubro_belongs_to_rubro_and_is_unique_per_rubro(tenant) -> None:
    estructura = Rubro.objects.create(name="ESTRUCTURA")
    albanileria = Rubro.objects.create(name="ALBAÑILERIA")

    Subrubro.objects.create(rubro=estructura, name="HORMIGON")
    # Mismo nombre en otro rubro está permitido.
    Subrubro.objects.create(rubro=albanileria, name="HORMIGON")

    # Pero no se puede repetir dentro del mismo rubro.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subrubro.objects.create(rubro=estructura, name="HORMIGON")


def test_unit_symbol_is_unique(tenant) -> None:
    Unit.objects.create(name="Metro cuadrado", symbol="m²", category=Unit.Category.AREA)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Unit.objects.create(name="Otra cosa", symbol="m²")


def test_business_component_name_is_unique(tenant) -> None:
    BusinessComponent.objects.create(name="TERRENO")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BusinessComponent.objects.create(name="TERRENO")


def test_subrubro_str_includes_rubro(tenant) -> None:
    r = Rubro.objects.create(name="ESTRUCTURA")
    s = Subrubro.objects.create(rubro=r, name="HORMIGON")
    assert str(s) == "ESTRUCTURA / HORMIGON"


def test_extraordinary_concept_same_name_different_type_allowed(tenant) -> None:
    ExtraordinaryConcept.objects.create(name="Préstamo", type=ExtraordinaryConcept.Type.INCOME)
    # Mismo nombre con type=expense está permitido.
    ExtraordinaryConcept.objects.create(name="Préstamo", type=ExtraordinaryConcept.Type.EXPENSE)
    # Pero no se puede repetir dentro del mismo type.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExtraordinaryConcept.objects.create(name="Préstamo", type=ExtraordinaryConcept.Type.INCOME)


def test_supplier_links_multiple_rubros(tenant) -> None:
    estructura = Rubro.objects.create(name="ESTRUCTURA")
    instalaciones = Rubro.objects.create(name="INSTALACIONES")
    s = Supplier.objects.create(name="CORRALON CENTRO", code="CRN001", category="CORRALON")
    s.rubros.add(estructura, instalaciones)
    assert s.rubros.count() == 2


def test_material_unique_per_unit_allows_same_name_other_unit(tenant) -> None:
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    kg = Unit.objects.create(name="Kilogramo", symbol="kg", category=Unit.Category.WEIGHT)
    bolsa = Unit.objects.create(name="Bolsa", symbol="bolsa", category=Unit.Category.OTHER)
    Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    # Mismo material en otra unidad: permitido.
    Material.objects.create(name="Cemento", rubro=rubro, unit=bolsa)
    # Repetir nombre+unidad: no.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Material.objects.create(name="Cemento", rubro=rubro, unit=kg)


def test_subcontract_unique_name(tenant) -> None:
    gl = Unit.objects.create(name="Global", symbol="GL", category=Unit.Category.GLOBAL)
    Subcontract.objects.create(name="Estudio de Suelo", unit=gl)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subcontract.objects.create(name="Estudio de Suelo", unit=gl)
