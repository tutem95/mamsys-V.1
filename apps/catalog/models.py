"""Catálogos base de Fase 2.

Esta primera entrega cubre los catálogos más fundamentales (sin dependencias
externas) que habilitan a las fases siguientes:

- Rubro: clasificación gruesa de trabajos (estructura, albañilería, etc.).
- Subrubro: subdivisión de un Rubro (FK estricta).
- Unit: unidad de medida (m², m³, JORNAL, UNI, ML, etc.).
- BusinessComponent: clasificador transversal (TERRENO, VENTA UF, etc.).

Catálogos pendientes que se suman en próximas entregas: Currency (SHARED),
Material, Supplier, Subcontract, Bank, BankAccount, Position, Team,
Warehouse, EmployeeStatus, ProjectStatus, ExtraordinaryConcept,
TrackingCategory, ExchangeRateType.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import CatalogItem


class Rubro(CatalogItem):
    """Clasificación gruesa de trabajos: TRABAJOS PRELIMINARES, ESTRUCTURA, etc."""

    class Meta(CatalogItem.Meta):
        verbose_name = "Rubro"
        verbose_name_plural = "Rubros"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="rubro_unique_name"),
        ]


class Subrubro(CatalogItem):
    """Subdivisión de un Rubro. Pertenece a un único Rubro (jerarquía estricta)."""

    rubro = models.ForeignKey(Rubro, on_delete=models.PROTECT, related_name="subrubros")

    class Meta(CatalogItem.Meta):
        verbose_name = "Subrubro"
        verbose_name_plural = "Subrubros"
        constraints = [
            models.UniqueConstraint(fields=["rubro", "name"], name="subrubro_unique_per_rubro"),
        ]

    def __str__(self) -> str:
        return f"{self.rubro.name} / {self.name}"


class Unit(CatalogItem):
    """Unidad de medida. El `name` es descriptivo, `symbol` lo que se muestra."""

    class Category(models.TextChoices):
        LENGTH = "length", "Longitud"
        AREA = "area", "Área"
        VOLUME = "volume", "Volumen"
        WEIGHT = "weight", "Peso"
        TIME = "time", "Tiempo"
        GLOBAL = "global", "Global"
        OTHER = "other", "Otro"

    symbol = models.CharField(max_length=20)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)

    class Meta(CatalogItem.Meta):
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"
        constraints = [
            models.UniqueConstraint(fields=["symbol"], name="unit_unique_symbol"),
        ]

    def __str__(self) -> str:
        return self.symbol


class BusinessComponent(CatalogItem):
    """Componente transversal de negocio (TERRENO, VENTA UF, etc.).

    No está atado a Rubro/Subrubro: cualquier operación puede combinar cualquier
    Componente con cualquier Subrubro.
    """

    class Meta(CatalogItem.Meta):
        verbose_name = "Componente"
        verbose_name_plural = "Componentes"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="businesscomponent_unique_name"),
        ]
