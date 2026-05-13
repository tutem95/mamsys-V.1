from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import BusinessComponent, Rubro, Subrubro, Unit


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
