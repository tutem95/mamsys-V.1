"""Importadores concretos.

Patrón: declarar columnas + implementar process_row(row, dry_run).
"""

from __future__ import annotations

from datetime import datetime
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


# ---------------------------------------------------------------------------
# Supplier (Proveedores)
# ---------------------------------------------------------------------------


class SupplierImporter(BaseImporter):
    slug = "supplier"
    label = "Proveedores"
    description = (
        "Proveedores con datos de contacto y vinculación a rubros. "
        "Para rubros múltiples separá por pipe: 'ESTRUCTURA|ALBAÑILERIA'."
    )
    columns = [
        ColumnSpec("name", "Nombre", required=True),
        ColumnSpec("code", "Código", help="Opcional."),
        ColumnSpec("category", "Categoría", help="Ej.: ARIDOS, CORRALON."),
        ColumnSpec("rubros", "Rubros (pipe-separated)", help="Ej.: 'ESTRUCTURA|ALBAÑILERIA'."),
        ColumnSpec("contact_name", "Contacto", help="Opcional."),
        ColumnSpec("email", "Email", help="Opcional."),
        ColumnSpec("phone", "Teléfono", help="Opcional."),
        ColumnSpec("address", "Dirección", help="Opcional."),
        ColumnSpec("tax_id", "CUIT", help="Opcional."),
        ColumnSpec("notes", "Notas", help="Opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        from apps.catalog.models import Supplier

        name = (row.get("name") or "").strip()
        if not name:
            raise ValueError("Nombre vacío.")
        code = (row.get("code") or "").strip()
        category = (row.get("category") or "").strip()
        rubros_raw = (row.get("rubros") or "").strip()
        contact_name = (row.get("contact_name") or "").strip()
        email = (row.get("email") or "").strip()
        phone = (row.get("phone") or "").strip()
        address = (row.get("address") or "").strip()
        tax_id = (row.get("tax_id") or "").strip()
        notes = (row.get("notes") or "").strip()

        rubro_objs = []
        if rubros_raw:
            rubro_names = [r.strip() for r in rubros_raw.split("|") if r.strip()]
            for rn in rubro_names:
                r = Rubro.objects.filter(name=rn).first()
                if r is None:
                    raise ValueError(f"Rubro '{rn}' no existe. Importalo primero.")
                rubro_objs.append(r)

        existing = Supplier.objects.filter(name=name).first()
        if existing:
            if dry_run:
                return ("updated", name)
            for field, value in [
                ("code", code), ("category", category), ("contact_name", contact_name),
                ("email", email), ("phone", phone), ("address", address),
                ("tax_id", tax_id), ("notes", notes),
            ]:
                if value:
                    setattr(existing, field, value)
            existing.save()
            if rubro_objs:
                existing.rubros.set(rubro_objs)
            return ("updated", name)
        if dry_run:
            return ("created", name)
        supplier = Supplier.objects.create(
            name=name, code=code, category=category,
            contact_name=contact_name, email=email, phone=phone,
            address=address, tax_id=tax_id, notes=notes,
        )
        if rubro_objs:
            supplier.rubros.set(rubro_objs)
        return ("created", name)


# ---------------------------------------------------------------------------
# Employee (laboral + personal + bancario en una sola fila)
# ---------------------------------------------------------------------------


class EmployeeImporter(BaseImporter):
    slug = "employee"
    label = "Empleados"
    description = (
        "Empleados con datos laborales, personales y bancarios. "
        "Identifica por (sociedad, internal_id) si está cargado; sino por "
        "(sociedad, nombre+apellido)."
    )
    columns = [
        ColumnSpec("first_name", "Nombre", required=True),
        ColumnSpec("last_name", "Apellido", required=True),
        ColumnSpec("company", "Sociedad (nombre)", required=True),
        ColumnSpec("internal_id", "ID interno", help="Recomendado, único por sociedad."),
        ColumnSpec("position", "Puesto (nombre)", help="Opcional."),
        ColumnSpec("status", "Estado (nombre)", help="Activo / Suspendido / etc."),
        ColumnSpec("hire_date", "Fecha de ingreso", help="YYYY-MM-DD."),
        ColumnSpec("arca_registered", "Alta ARCA", help="True/False, 1/0, si/no."),
        ColumnSpec("document_type", "Tipo doc", help="DNI / PAS / OTHER. Default DNI."),
        ColumnSpec("document_number", "Nº documento", help="Opcional."),
        ColumnSpec("cuil", "CUIL", help="Opcional."),
        ColumnSpec("birth_date", "Fecha nacimiento", help="YYYY-MM-DD opcional."),
        ColumnSpec("nationality", "Nacionalidad", help="Opcional."),
        ColumnSpec("phone_mobile", "Celular", help="Opcional."),
        ColumnSpec("email", "Email personal", help="Opcional."),
        ColumnSpec("address", "Dirección", help="Opcional."),
        ColumnSpec("bank", "Banco (nombre)", help="Opcional."),
        ColumnSpec("cbu", "CBU", help="Opcional."),
        ColumnSpec("cvu", "CVU billetera", help="Opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        from apps.catalog.models import Bank, EmployeeStatus, Position
        from apps.companies.models import Company
        from apps.payroll.models import (
            Employee,
            EmployeeBanking,
            EmployeePersonalData,
        )

        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        company_name = (row.get("company") or "").strip()
        if not first_name or not last_name or not company_name:
            raise ValueError("Nombre, apellido y sociedad son obligatorios.")

        company = Company.objects.filter(name=company_name).first()
        if company is None:
            raise ValueError(f"Sociedad '{company_name}' no existe.")

        internal_id = (row.get("internal_id") or "").strip()
        position_name = (row.get("position") or "").strip()
        status_name = (row.get("status") or "").strip()

        position = None
        if position_name:
            position = Position.objects.filter(name=position_name).first()
            if position is None:
                raise ValueError(f"Puesto '{position_name}' no existe.")
        status = None
        if status_name:
            status = EmployeeStatus.objects.filter(name=status_name).first()
            if status is None:
                raise ValueError(f"Estado '{status_name}' no existe.")

        hire_date = _parse_date(row.get("hire_date")) if row.get("hire_date") else None
        arca = _parse_bool(row.get("arca_registered"))

        existing = None
        if internal_id:
            existing = Employee.objects.filter(company=company, internal_id=internal_id).first()
        if existing is None:
            existing = (
                Employee.objects
                .filter(
                    company=company,
                    personal_data__first_name=first_name,
                    personal_data__last_name=last_name,
                )
                .first()
            )

        action = "updated" if existing else "created"
        label = f"{first_name} {last_name}"
        if dry_run:
            return (action, label)

        emp = existing or Employee(company=company)
        emp.internal_id = internal_id
        if position:
            emp.position = position
        if status:
            emp.status = status
        if hire_date:
            emp.hire_date = hire_date
        emp.arca_registered = arca
        emp.save()

        personal = getattr(emp, "personal_data", None) or EmployeePersonalData(employee=emp)
        personal.first_name = first_name
        personal.last_name = last_name
        doc_type = (row.get("document_type") or "").strip().upper() or Employee.DocumentType.DNI
        if doc_type not in {c[0] for c in Employee.DocumentType.choices}:
            doc_type = Employee.DocumentType.DNI
        personal.document_type = doc_type
        personal.document_number = (row.get("document_number") or "").strip()
        personal.cuil = (row.get("cuil") or "").strip()
        bd = _parse_date(row.get("birth_date")) if row.get("birth_date") else None
        if bd:
            personal.birth_date = bd
        personal.nationality = (row.get("nationality") or "").strip()
        personal.phone_mobile = (row.get("phone_mobile") or "").strip()
        personal.email = (row.get("email") or "").strip()
        personal.address = (row.get("address") or "").strip()
        personal.save()

        bank_name = (row.get("bank") or "").strip()
        cbu = (row.get("cbu") or "").strip()
        cvu = (row.get("cvu") or "").strip()
        if bank_name or cbu or cvu:
            bank = None
            if bank_name:
                bank = Bank.objects.filter(name=bank_name).first()
                if bank is None:
                    raise ValueError(f"Banco '{bank_name}' no existe.")
            banking = getattr(emp, "banking", None) or EmployeeBanking(employee=emp)
            if bank:
                banking.bank = bank
            banking.cbu = cbu
            banking.cvu_mercado_libre = cvu
            banking.save()

        return (action, label)


# ---------------------------------------------------------------------------
# ExchangeRate (cotizaciones diarias)
# ---------------------------------------------------------------------------


class ExchangeRateImporter(BaseImporter):
    slug = "exchange_rate"
    label = "Cotizaciones"
    description = (
        "Cotizaciones diarias para un tipo (BNA, CCL, etc.). El tipo debe existir "
        "previamente. Una fila por (tipo, fecha)."
    )
    columns = [
        ColumnSpec("rate_type", "Tipo (nombre)", required=True, help="Ej.: BNA, CCL."),
        ColumnSpec("date", "Fecha", required=True, help="YYYY-MM-DD o DD/MM/YYYY."),
        ColumnSpec("rate", "Cotización", required=True, help="Acepta coma decimal."),
        ColumnSpec("source", "Origen", help="manual / imported / calculated. Default imported."),
        ColumnSpec("notes", "Notas", help="Opcional."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        from apps.pricing.models import ExchangeRate, ExchangeRateType

        type_name = (row.get("rate_type") or "").strip()
        date_raw = row.get("date")
        rate_raw = row.get("rate")
        if not type_name or not date_raw or rate_raw in (None, "", " "):
            raise ValueError("rate_type, date y rate son obligatorios.")

        rate_type = ExchangeRateType.objects.filter(name=type_name).first()
        if rate_type is None:
            raise ValueError(f"Tipo de cotización '{type_name}' no existe.")

        date_value = _parse_date(date_raw)
        if date_value is None:
            raise ValueError(f"Fecha inválida: '{date_raw}'. Usá YYYY-MM-DD o DD/MM/YYYY.")

        try:
            rate_value = Decimal(str(rate_raw).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Cotización inválida: '{rate_raw}'.")

        source_raw = (row.get("source") or "imported").strip().lower()
        if source_raw not in {c[0] for c in ExchangeRate.Source.choices}:
            source_raw = ExchangeRate.Source.IMPORTED
        notes = (row.get("notes") or "").strip()

        existing = ExchangeRate.objects.filter(rate_type=rate_type, date=date_value).first()
        label = f"{type_name} @ {date_value}"
        if existing:
            if dry_run:
                return ("updated", label)
            existing.rate = rate_value
            existing.source = source_raw
            existing.notes = notes
            existing.save(update_fields=["rate", "source", "notes", "updated_at"])
            return ("updated", label)
        if dry_run:
            return ("created", label)
        ExchangeRate.objects.create(
            rate_type=rate_type, date=date_value, rate=rate_value,
            source=source_raw, notes=notes,
        )
        return ("created", label)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _parse_date(raw):
    if raw is None:
        return None
    if hasattr(raw, "year") and hasattr(raw, "month"):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(raw) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    return s in {"1", "true", "yes", "si", "sí", "y", "t"}


# Registro central
IMPORTERS: dict[str, type[BaseImporter]] = {
    RubroImporter.slug: RubroImporter,
    SubrubroImporter.slug: SubrubroImporter,
    MaterialImporter.slug: MaterialImporter,
    SupplierImporter.slug: SupplierImporter,
    EmployeeImporter.slug: EmployeeImporter,
    ExchangeRateImporter.slug: ExchangeRateImporter,
}


def get_importer(slug: str) -> BaseImporter | None:
    cls = IMPORTERS.get(slug)
    return cls() if cls else None
