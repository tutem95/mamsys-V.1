"""Importadores concretos.

Por ahora:
- RubroImporter: nombre + código opcional.
- SubrubroImporter: rubro (nombre) + nombre del subrubro.
- MaterialImporter: nombre + rubro (nombre) + unidad (símbolo) +
  subrubro opcional + descripción opcional + último precio opcional.

Patrón para sumar más: declarar columnas + implementar process_row.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.catalog.models import Material, Rubro, Subrubro, Unit

from .base import BaseImporter, ColumnSpec


class RubroImporter(BaseImporter):
    slug = "rubro"
    label = "Rubros"
    description = "Listado simple de rubros (nombre + código opcional)."
    columns = [
        ColumnSpec("name", "Nombre", required=True),
        ColumnSpec("code", "Código", help="Opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        name = (row.get("name") or "").strip()
        code = (row.get("code") or "").strip()
        if not name:
            raise ValueError("Nombre vacío.")
        existing = Rubro.objects.filter(name=name).first()
        if existing:
            if dry_run:
                return ("updated", name)
            existing.code = code or existing.code
            existing.save(update_fields=["code", "updated_at"])
            return ("updated", name)
        if dry_run:
            return ("created", name)
        Rubro.objects.create(name=name, code=code)
        return ("created", name)


class SubrubroImporter(BaseImporter):
    slug = "subrubro"
    label = "Subrubros"
    description = "Subrubros con rubro padre (por nombre)."
    columns = [
        ColumnSpec("rubro", "Rubro (nombre)", required=True),
        ColumnSpec("name", "Nombre del subrubro", required=True),
        ColumnSpec("code", "Código", help="Opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        rubro_name = (row.get("rubro") or "").strip()
        name = (row.get("name") or "").strip()
        code = (row.get("code") or "").strip()
        if not name or not rubro_name:
            raise ValueError("Nombre o rubro vacíos.")
        rubro = Rubro.objects.filter(name=rubro_name).first()
        if rubro is None:
            raise ValueError(f"Rubro '{rubro_name}' no existe. Importalo primero.")
        existing = Subrubro.objects.filter(rubro=rubro, name=name).first()
        label = f"{rubro_name} / {name}"
        if existing:
            if dry_run:
                return ("updated", label)
            existing.code = code or existing.code
            existing.save(update_fields=["code", "updated_at"])
            return ("updated", label)
        if dry_run:
            return ("created", label)
        Subrubro.objects.create(rubro=rubro, name=name, code=code)
        return ("created", label)


class MaterialImporter(BaseImporter):
    slug = "material"
    label = "Materiales"
    description = "Materiales con rubro y unidad. Subrubro y último precio son opcionales."
    columns = [
        ColumnSpec("name", "Nombre", required=True),
        ColumnSpec("rubro", "Rubro (nombre)", required=True),
        ColumnSpec("unit", "Unidad (símbolo)", required=True),
        ColumnSpec("subrubro", "Subrubro", help="Opcional."),
        ColumnSpec("description", "Descripción", help="Opcional."),
        ColumnSpec("last_price", "Último precio", help="Decimal opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        name = (row.get("name") or "").strip()
        rubro_name = (row.get("rubro") or "").strip()
        unit_symbol = (row.get("unit") or "").strip()
        subrubro_name = (row.get("subrubro") or "").strip()
        description = (row.get("description") or "").strip()
        last_price_raw = row.get("last_price")

        if not name or not rubro_name or not unit_symbol:
            raise ValueError("Nombre, rubro y unidad son obligatorios.")

        rubro = Rubro.objects.filter(name=rubro_name).first()
        if rubro is None:
            raise ValueError(f"Rubro '{rubro_name}' no existe. Importalo primero.")
        unit = Unit.objects.filter(symbol=unit_symbol).first()
        if unit is None:
            raise ValueError(f"Unidad con símbolo '{unit_symbol}' no existe. Cargala primero.")
        subrubro = None
        if subrubro_name:
            subrubro = Subrubro.objects.filter(rubro=rubro, name=subrubro_name).first()
            if subrubro is None:
                raise ValueError(
                    f"Subrubro '{subrubro_name}' no existe bajo el rubro '{rubro_name}'.",
                )

        last_price = None
        if last_price_raw not in (None, "", " "):
            try:
                last_price = Decimal(str(last_price_raw).replace(",", "."))
            except (InvalidOperation, ValueError):
                raise ValueError(f"Último precio inválido: '{last_price_raw}'.")

        existing = Material.objects.filter(name=name, unit=unit).first()
        if existing:
            if dry_run:
                return ("updated", name)
            existing.rubro = rubro
            existing.subrubro = subrubro
            existing.description = description or existing.description
            if last_price is not None:
                existing.last_known_price = last_price
            existing.save()
            return ("updated", name)
        if dry_run:
            return ("created", name)
        Material.objects.create(
            name=name, rubro=rubro, subrubro=subrubro, unit=unit,
            description=description, last_known_price=last_price,
        )
        return ("created", name)


# Registro central
IMPORTERS: dict[str, type[BaseImporter]] = {
    RubroImporter.slug: RubroImporter,
    SubrubroImporter.slug: SubrubroImporter,
    MaterialImporter.slug: MaterialImporter,
}


def get_importer(slug: str) -> BaseImporter | None:
    cls = IMPORTERS.get(slug)
    return cls() if cls else None
