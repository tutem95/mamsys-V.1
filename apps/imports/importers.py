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


class UnitImporter(BaseImporter):
    slug = "unit"
    label = "Unidades"
    description = "Unidades de medida (nombre + símbolo único + categoría)."
    columns = [
        ColumnSpec("symbol", "Símbolo", required=True, help="Identificador único. Ej.: m2, kg, JORNAL."),
        ColumnSpec("name", "Nombre", required=True),
        ColumnSpec("category", "Categoría", help="length/area/volume/weight/time/global/other. Default other."),
    ]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        symbol = (row.get("symbol") or "").strip()
        name = (row.get("name") or "").strip()
        if not symbol or not name:
            raise ValueError("Símbolo y nombre son obligatorios.")
        category = (row.get("category") or "").strip().lower() or Unit.Category.OTHER
        if category not in {c[0] for c in Unit.Category.choices}:
            category = Unit.Category.OTHER

        existing = Unit.objects.filter(symbol=symbol).first()
        if existing:
            if dry_run:
                return ("updated", symbol)
            existing.name = name
            existing.category = category
            existing.save(update_fields=["name", "category", "updated_at"])
            return ("updated", symbol)
        if dry_run:
            return ("created", symbol)
        Unit.objects.create(symbol=symbol, name=name, category=category)
        return ("created", symbol)


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


# ---------------------------------------------------------------------------
# Purchase (compras históricas — cabecera + items en el mismo archivo)
# ---------------------------------------------------------------------------


class PurchaseImporter(BaseImporter):
    """Compras agrupadas por (supplier, document_number).

    Cada fila trae los campos de cabecera (redundantes dentro del grupo) +
    opcionalmente los datos del ítem. El primer row del grupo define la
    cabecera; los subsiguientes solo aportan items si traen material+qty.

    Idempotente: si ya existe una Purchase con (supplier, document_number),
    se actualiza la cabecera y se REEMPLAZAN sus items (sino habría
    duplicación al re-importar). Esto significa que NO se mezclan items
    de varias importaciones — el archivo es la fuente de verdad de items.
    """

    slug = "purchase"
    label = "Compras históricas"
    description = (
        "Compras con cabecera + items. Una fila por item (o por compra sin items). "
        "Las filas con el mismo `document_number` y `supplier` se agrupan en una "
        "sola Purchase. Idempotente: re-importar reemplaza los items existentes."
    )
    columns = [
        ColumnSpec("document_number", "Nº comprobante", required=True),
        ColumnSpec("invoice_date", "Fecha factura", required=True, help="YYYY-MM-DD o DD/MM/YYYY."),
        ColumnSpec("supplier", "Proveedor (nombre)", required=True),
        ColumnSpec("company", "Sociedad (nombre)", required=True),
        ColumnSpec("rubro", "Rubro (nombre)", required=True),
        ColumnSpec("currency", "Moneda (código)", required=True, help="ARS, USD, EUR…"),
        ColumnSpec("total_amount", "Total c/IVA", required=True, help="Acepta coma decimal."),
        ColumnSpec("document_type", "Tipo doc", help="factura_a/b/c, presupuesto, remito, ticket, otro."),
        ColumnSpec("purchase_type", "Tipo compra", help="obra / admin / cadeteria. Default obra."),
        ColumnSpec("project", "Obra (nombre)", help="Requerido si purchase_type=obra."),
        ColumnSpec("subrubro", "Subrubro", help="Opcional."),
        ColumnSpec("is_subcontract", "Subcontrato", help="True si toda la compra es un subcontrato."),
        ColumnSpec("amount_without_tax", "Subtotal sin IVA", help="Opcional."),
        ColumnSpec("iva_21", "IVA 21%", help="Opcional."),
        ColumnSpec("iva_10_5", "IVA 10,5%", help="Opcional."),
        ColumnSpec("perc_iibb", "Perc. IIBB", help="Opcional."),
        ColumnSpec("status", "Estado", help="draft/to_pay/paid_partial/paid/cancelled. Default to_pay."),
        ColumnSpec("payment_method", "Forma de pago", help="Opcional."),
        ColumnSpec("week_to_pay", "Semana de pago", help="Opcional."),
        ColumnSpec("due_date", "Vencimiento", help="YYYY-MM-DD opcional."),
        ColumnSpec("detail", "Detalle", help="Descripción de la compra."),
        ColumnSpec("notes", "Observaciones", help="Opcional."),
        ColumnSpec("item_material", "Material (nombre)", help="Vacío si no hay item en esta fila."),
        ColumnSpec("item_quantity", "Cantidad", help="Decimal."),
        ColumnSpec("item_unit", "Unidad ítem (símbolo)", help="Si vacío usa unidad del material."),
        ColumnSpec("item_unit_price", "Precio unitario", help="Decimal."),
        ColumnSpec("item_subcontract", "Subcontrato (nombre)", help="Si is_subcontract=True."),
    ]

    def run(self, rows: list[dict], dry_run: bool = True):
        from collections import defaultdict

        from .base import ImportResult, RowError

        result = ImportResult(rows_total=0)

        groups: dict[tuple, list[tuple[int, dict]]] = defaultdict(list)
        for idx, row in enumerate(rows, start=2):
            supplier_name = (row.get("supplier") or "").strip()
            doc_number = (row.get("document_number") or "").strip()
            if not supplier_name or not doc_number:
                result.errors.append(RowError(
                    row=idx,
                    message="Faltan supplier o document_number para agrupar.",
                ))
                continue
            key = (supplier_name.upper(), doc_number.upper())
            groups[key].append((idx, row))

        result.rows_total = len(groups)

        for key, group_rows in groups.items():
            first_idx = group_rows[0][0]
            try:
                action, label = self._process_group(group_rows, dry_run)
                if action == "created":
                    result.rows_created += 1
                    result.rows_ok += 1
                elif action == "updated":
                    result.rows_updated += 1
                    result.rows_ok += 1
                if len(result.preview) < 20:
                    result.preview.append({"row": first_idx, "action": action, "value": label})
            except ValueError as exc:
                result.errors.append(RowError(row=first_idx, message=str(exc)))

        return result

    def _process_group(self, group_rows, dry_run):
        from django.db import transaction

        with transaction.atomic():
            return self._process_group_inner(group_rows, dry_run)

    def _process_group_inner(self, group_rows, dry_run):
        from apps.catalog.models import (
            Material,
            Subcontract,
            Supplier,
            Unit,
        )
        from apps.companies.models import Company
        from apps.currencies.models import Currency
        from apps.procurement.models import Purchase, PurchaseItem
        from apps.projects.models import Project

        header_row = group_rows[0][1]
        doc_number = (header_row.get("document_number") or "").strip()
        supplier_name = (header_row.get("supplier") or "").strip()
        company_name = (header_row.get("company") or "").strip()
        rubro_name = (header_row.get("rubro") or "").strip()
        currency_code = (header_row.get("currency") or "").strip().upper()
        invoice_date = _parse_date(header_row.get("invoice_date"))
        total_amount = _parse_decimal(header_row.get("total_amount"))

        if not all([doc_number, supplier_name, company_name, rubro_name, currency_code]):
            raise ValueError("Faltan campos requeridos de cabecera.")
        if invoice_date is None:
            raise ValueError(f"Fecha de factura inválida: '{header_row.get('invoice_date')}'.")
        if total_amount is None:
            raise ValueError(f"Total inválido: '{header_row.get('total_amount')}'.")

        supplier = Supplier.objects.filter(name=supplier_name).first()
        if supplier is None:
            raise ValueError(f"Proveedor '{supplier_name}' no existe.")
        company = Company.objects.filter(name=company_name).first()
        if company is None:
            raise ValueError(f"Sociedad '{company_name}' no existe.")
        rubro = Rubro.objects.filter(name=rubro_name).first()
        if rubro is None:
            raise ValueError(f"Rubro '{rubro_name}' no existe.")
        currency = Currency.objects.filter(code=currency_code).first()
        if currency is None:
            raise ValueError(f"Moneda '{currency_code}' no existe.")

        subrubro = None
        subrubro_name = (header_row.get("subrubro") or "").strip()
        if subrubro_name:
            subrubro = Subrubro.objects.filter(rubro=rubro, name=subrubro_name).first()
            if subrubro is None:
                raise ValueError(f"Subrubro '{subrubro_name}' no existe bajo '{rubro_name}'.")

        project = None
        project_name = (header_row.get("project") or "").strip()
        if project_name:
            project = Project.objects.filter(name=project_name).first()
            if project is None:
                raise ValueError(f"Obra '{project_name}' no existe.")

        purchase_type = (header_row.get("purchase_type") or "obra").strip().lower()
        if purchase_type not in {c[0] for c in Purchase.PurchaseType.choices}:
            purchase_type = Purchase.PurchaseType.OBRA
        if purchase_type == Purchase.PurchaseType.OBRA and project is None:
            raise ValueError("purchase_type=obra requiere campo `project`.")

        document_type = (header_row.get("document_type") or "factura_a").strip().lower()
        if document_type not in {c[0] for c in Purchase.DocumentType.choices}:
            document_type = Purchase.DocumentType.FACTURA_A

        is_subcontract = _parse_bool(header_row.get("is_subcontract"))
        status = (header_row.get("status") or "to_pay").strip().lower()
        if status not in {c[0] for c in Purchase.Status.choices}:
            status = Purchase.Status.TO_PAY

        amount_without_tax = _parse_decimal(header_row.get("amount_without_tax")) or Decimal("0")
        iva_21 = _parse_decimal(header_row.get("iva_21")) or Decimal("0")
        iva_10_5 = _parse_decimal(header_row.get("iva_10_5")) or Decimal("0")
        perc_iibb = _parse_decimal(header_row.get("perc_iibb")) or Decimal("0")

        payment_method = (header_row.get("payment_method") or "").strip()
        week_to_pay = (header_row.get("week_to_pay") or "").strip()
        due_date = _parse_date(header_row.get("due_date")) if header_row.get("due_date") else None
        detail = (header_row.get("detail") or "").strip()
        notes = (header_row.get("notes") or "").strip()

        label = f"{doc_number} · {supplier_name}"

        existing = (
            Purchase.objects
            .filter(supplier=supplier, document_number=doc_number)
            .first()
        )
        action = "updated" if existing else "created"

        if dry_run:
            return (action, label)

        purchase_data = dict(
            purchase_type=purchase_type,
            document_type=document_type,
            document_number=doc_number,
            invoice_date=invoice_date,
            is_subcontract=is_subcontract,
            supplier=supplier,
            company=company,
            project=project,
            rubro=rubro,
            subrubro=subrubro,
            detail=detail,
            original_currency=currency,
            amount_without_tax=amount_without_tax,
            iva_21=iva_21,
            iva_10_5=iva_10_5,
            perc_iibb=perc_iibb,
            total_amount=total_amount,
            payment_method=payment_method,
            week_to_pay=week_to_pay,
            due_date=due_date,
            status=status,
            notes=notes,
        )

        if existing:
            for field, value in purchase_data.items():
                setattr(existing, field, value)
            existing.save()
            purchase = existing
            purchase.items.all().delete()
        else:
            purchase = Purchase.objects.create(**purchase_data)

        items_created = 0
        for _idx, row in group_rows:
            item_material = (row.get("item_material") or "").strip()
            item_subcontract = (row.get("item_subcontract") or "").strip()
            if not (item_material or item_subcontract):
                continue
            qty = _parse_decimal(row.get("item_quantity"))
            unit_price = _parse_decimal(row.get("item_unit_price"))
            if qty is None or unit_price is None:
                raise ValueError(
                    f"Item con material/subcontract pero sin cantidad o precio "
                    f"({item_material or item_subcontract}).",
                )

            unit_symbol = (row.get("item_unit") or "").strip()
            material = sub_obj = None
            unit = None
            if item_material:
                material = Material.objects.filter(name=item_material).first()
                if material is None:
                    raise ValueError(f"Material '{item_material}' no existe.")
                unit = (
                    Unit.objects.filter(symbol=unit_symbol).first()
                    if unit_symbol else material.unit
                )
            if item_subcontract:
                sub_obj = Subcontract.objects.filter(name=item_subcontract).first()
                if sub_obj is None:
                    raise ValueError(f"Subcontract '{item_subcontract}' no existe.")
                unit = (
                    Unit.objects.filter(symbol=unit_symbol).first()
                    if unit_symbol else sub_obj.unit
                )
            if unit is None:
                raise ValueError("No se pudo resolver la unidad del item.")

            PurchaseItem.objects.create(
                purchase=purchase,
                material=material,
                subcontract=sub_obj,
                quantity=qty,
                unit=unit,
                unit_price=unit_price,
            )
            items_created += 1

        label = f"{label} ({items_created} ítem{'s' if items_created != 1 else ''})"
        return (action, label)


def _parse_decimal(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# PayrollPeriod (quincenas históricas: cabecera + entries por empleado)
# ---------------------------------------------------------------------------


class PayrollPeriodImporter(BaseImporter):
    """Quincenas históricas con cabecera + entrada por empleado.

    Cada fila trae la cabecera (redundante dentro del grupo) + datos del
    empleado para esa quincena. Las filas con misma (company, year, month,
    period_number) se agrupan en una sola PayrollPeriod.

    Idempotente: re-importar actualiza la cabecera y upserts cada
    PayrollEntry por (period, employee). No borra entries previas de la
    quincena que no estén en el archivo (cuidado al re-importar archivos
    parciales — los empleados omitidos quedan con sus valores anteriores).

    Imputación a obras (PayrollAllocation) NO se importa acá; se carga
    manualmente desde la UI de cada entry. Para historial pasamos sin
    imputar (los KPIs por obra solo aplican desde acá en adelante).
    """

    slug = "payroll_period"
    label = "Quincenas históricas"
    description = (
        "Quincenas con cabecera + una fila por empleado. Las filas con "
        "misma (sociedad, año, mes, número de quincena) se agrupan en una "
        "PayrollPeriod. Idempotente por (sociedad, año, mes, periodo)."
    )
    columns = [
        # Cabecera
        ColumnSpec("company", "Sociedad (nombre)", required=True),
        ColumnSpec("year", "Año", required=True),
        ColumnSpec("month", "Mes", required=True, help="1-12."),
        ColumnSpec("period_number", "Nº quincena", required=True, help="1 o 2."),
        ColumnSpec("start_date", "Inicio", required=True, help="YYYY-MM-DD."),
        ColumnSpec("end_date", "Fin", required=True, help="YYYY-MM-DD."),
        ColumnSpec("talonario_name", "Talonario", help="Ej.: '1era Quincena Mayo'."),
        ColumnSpec("working_days", "Días L-V", help="Default 10."),
        ColumnSpec("saturdays", "Sábados", help="Default 2."),
        ColumnSpec("holidays", "Feriados", help="Default 0."),
        ColumnSpec("total_days", "Días total", help="Default 12."),
        ColumnSpec("hours_weekday", "Horas L-V", help="Default 8."),
        ColumnSpec("hours_saturday", "Horas sábado", help="Default 7."),
        ColumnSpec("total_hours", "Horas total", help="Default 94."),
        ColumnSpec("plus_overtime_pct", "% Plus H.Extra", help="Ej.: 12 → 12%."),
        ColumnSpec("plus_presentismo_pct", "% Plus Presentismo", help="Ej.: 2.3 → 2.30%."),
        ColumnSpec("status", "Estado", help="open/closed/paid. Default closed (histórico)."),
        # Entrada (por empleado)
        ColumnSpec("employee_internal_id", "ID empleado", help="Usar este o employee_name."),
        ColumnSpec("employee_first_name", "Nombre", help="Si no hay internal_id."),
        ColumnSpec("employee_last_name", "Apellido", help="Si no hay internal_id."),
        ColumnSpec("value_jornal", "Valor jornal", help="Decimal por día trabajado."),
        ColumnSpec("days_worked", "Días trabajados", help="Default total_days de la quincena."),
        ColumnSpec("absences", "Faltas", help="Default 0."),
        ColumnSpec("justified_absences", "Justificadas", help="Default 0."),
        ColumnSpec("vacations", "Vacaciones (días)", help="Default 0."),
        ColumnSpec("vacations_amount", "Vacaciones $", help="Default 0."),
        ColumnSpec("late_hours", "H. tarde", help="Default 0."),
        ColumnSpec("late_hours_amount", "H. tarde $", help="Default 0."),
        ColumnSpec("overtime_hours", "H. extra", help="Default 0."),
        ColumnSpec("bank_amount", "Banco $", help="Resto cae en efectivo."),
        ColumnSpec("receipt_observations", "Observaciones recibo", help="Opcional."),
    ]

    def run(self, rows: list[dict], dry_run: bool = True):
        from collections import defaultdict

        from .base import ImportResult, RowError

        result = ImportResult(rows_total=0)

        groups: dict[tuple, list[tuple[int, dict]]] = defaultdict(list)
        for idx, row in enumerate(rows, start=2):
            try:
                company_name = (row.get("company") or "").strip()
                year = int(str(row.get("year") or "").strip())
                month = int(str(row.get("month") or "").strip())
                period_number = int(str(row.get("period_number") or "").strip())
            except (ValueError, TypeError):
                result.errors.append(RowError(
                    row=idx,
                    message="Faltan o son inválidos: company, year, month, period_number.",
                ))
                continue
            if not company_name:
                result.errors.append(RowError(row=idx, message="company vacío."))
                continue
            key = (company_name.upper(), year, month, period_number)
            groups[key].append((idx, row))

        result.rows_total = len(groups)

        for key, group_rows in groups.items():
            first_idx = group_rows[0][0]
            try:
                action, label, entries_count = self._process_group(group_rows, dry_run)
                if action == "created":
                    result.rows_created += 1
                    result.rows_ok += 1
                elif action == "updated":
                    result.rows_updated += 1
                    result.rows_ok += 1
                if len(result.preview) < 20:
                    result.preview.append({
                        "row": first_idx, "action": action,
                        "value": f"{label} · {entries_count} empleado(s)",
                    })
            except ValueError as exc:
                result.errors.append(RowError(row=first_idx, message=str(exc)))

        return result

    def _process_group(self, group_rows, dry_run):
        from django.db import transaction

        with transaction.atomic():
            return self._process_group_inner(group_rows, dry_run)

    def _process_group_inner(self, group_rows, dry_run):
        from apps.companies.models import Company
        from apps.currencies.models import Currency
        from apps.payroll.models import PayrollEntry, PayrollPeriod

        header_row = group_rows[0][1]
        company_name = (header_row.get("company") or "").strip()
        year = int(str(header_row.get("year")).strip())
        month = int(str(header_row.get("month")).strip())
        period_number = int(str(header_row.get("period_number")).strip())
        start_date = _parse_date(header_row.get("start_date"))
        end_date = _parse_date(header_row.get("end_date"))

        if start_date is None or end_date is None:
            raise ValueError("start_date y end_date son obligatorios.")
        if not (1 <= month <= 12):
            raise ValueError(f"Mes inválido: {month}.")
        if period_number not in (1, 2):
            raise ValueError(f"period_number debe ser 1 o 2 (vino {period_number}).")

        company = Company.objects.filter(name=company_name).first()
        if company is None:
            raise ValueError(f"Sociedad '{company_name}' no existe.")

        # Defaults para campos numéricos.
        defaults_int = {
            "working_days": 10, "saturdays": 2, "holidays": 0, "total_days": 12,
            "hours_weekday": 8, "hours_saturday": 7, "total_hours": 94,
        }
        period_data = {}
        for key, default in defaults_int.items():
            raw = header_row.get(key)
            period_data[key] = int(str(raw).strip()) if raw not in (None, "", " ") else default

        period_data["plus_overtime_pct"] = _parse_decimal(header_row.get("plus_overtime_pct")) or Decimal("0")
        period_data["plus_presentismo_pct"] = _parse_decimal(header_row.get("plus_presentismo_pct")) or Decimal("0")
        period_data["start_date"] = start_date
        period_data["end_date"] = end_date
        period_data["talonario_name"] = (header_row.get("talonario_name") or "").strip()

        status = (header_row.get("status") or "closed").strip().lower()
        if status not in {c[0] for c in PayrollPeriod.Status.choices}:
            status = PayrollPeriod.Status.CLOSED
        period_data["status"] = status

        label = f"P{period_number} {month:02d}/{year} · {company_name}"

        existing = PayrollPeriod.objects.filter(
            company=company, year=year, month=month, period_number=period_number,
        ).first()
        action = "updated" if existing else "created"

        if dry_run:
            return (action, label, len([r for r in group_rows if _row_has_employee_data(r[1])]))

        if existing:
            period = existing
            for k, v in period_data.items():
                setattr(period, k, v)
            period.save()
        else:
            period = PayrollPeriod.objects.create(
                company=company, year=year, month=month, period_number=period_number,
                **period_data,
            )

        # Procesar entries.
        ars = Currency.objects.get(code="ARS")
        entries_count = 0
        for _idx, row in group_rows:
            if not _row_has_employee_data(row):
                continue
            employee = self._resolve_employee(row, company)
            if employee is None:
                raise ValueError(self._employee_label(row) + " no se encontró.")

            value_jornal = _parse_decimal(row.get("value_jornal")) or Decimal("0")
            days_worked = _parse_decimal(row.get("days_worked"))
            if days_worked is None:
                days_worked = Decimal(period_data.get("total_days", 12))

            entry_defaults = {
                "currency": employee.last_known_currency or ars,
                "value_jornal": value_jornal,
                "days_worked": days_worked,
                "absences": _parse_decimal(row.get("absences")) or Decimal("0"),
                "justified_absences": _parse_decimal(row.get("justified_absences")) or Decimal("0"),
                "vacations": _parse_decimal(row.get("vacations")) or Decimal("0"),
                "vacations_amount": _parse_decimal(row.get("vacations_amount")) or Decimal("0"),
                "late_hours": _parse_decimal(row.get("late_hours")) or Decimal("0"),
                "late_hours_amount": _parse_decimal(row.get("late_hours_amount")) or Decimal("0"),
                "overtime_hours": _parse_decimal(row.get("overtime_hours")) or Decimal("0"),
                "bank_amount": _parse_decimal(row.get("bank_amount")) or Decimal("0"),
                "receipt_observations": (row.get("receipt_observations") or "").strip(),
            }

            entry = PayrollEntry.objects.filter(payroll_period=period, employee=employee).first()
            if entry is None:
                entry = PayrollEntry(payroll_period=period, employee=employee)
            for k, v in entry_defaults.items():
                setattr(entry, k, v)
            entry.save()  # dispara recalculate() en cascada
            entries_count += 1

        return (action, label, entries_count)

    def _resolve_employee(self, row: dict, company):
        from apps.payroll.models import Employee

        internal_id = (row.get("employee_internal_id") or "").strip()
        if internal_id:
            return Employee.objects.filter(company=company, internal_id=internal_id).first()
        first_name = (row.get("employee_first_name") or "").strip()
        last_name = (row.get("employee_last_name") or "").strip()
        if not (first_name and last_name):
            return None
        return (
            Employee.objects.filter(
                company=company,
                personal_data__first_name=first_name,
                personal_data__last_name=last_name,
            )
            .first()
        )

    def _employee_label(self, row: dict) -> str:
        internal_id = (row.get("employee_internal_id") or "").strip()
        if internal_id:
            return f"Empleado #{internal_id}"
        first_name = (row.get("employee_first_name") or "").strip()
        last_name = (row.get("employee_last_name") or "").strip()
        return f"{first_name} {last_name}".strip() or "Empleado sin identificar"


def _row_has_employee_data(row: dict) -> bool:
    return bool(
        (row.get("employee_internal_id") or "").strip()
        or ((row.get("employee_first_name") or "").strip() and (row.get("employee_last_name") or "").strip())
    )


# Registro central
IMPORTERS: dict[str, type[BaseImporter]] = {
    RubroImporter.slug: RubroImporter,
    SubrubroImporter.slug: SubrubroImporter,
    UnitImporter.slug: UnitImporter,
    MaterialImporter.slug: MaterialImporter,
    SupplierImporter.slug: SupplierImporter,
    EmployeeImporter.slug: EmployeeImporter,
    ExchangeRateImporter.slug: ExchangeRateImporter,
    PurchaseImporter.slug: PurchaseImporter,
    PayrollPeriodImporter.slug: PayrollPeriodImporter,
}


def get_importer(slug: str) -> BaseImporter | None:
    cls = IMPORTERS.get(slug)
    return cls() if cls else None
