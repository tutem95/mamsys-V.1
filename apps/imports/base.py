"""Base class para importadores.

Convenciones:
- Cada Importer declara `slug`, `label`, `columns` (list de field specs).
- El usuario sube un CSV o XLSX. El parser unifica a lista de dicts.
- run(dry_run=True/False) procesa cada fila, valida, y guarda si no es dry-run.
- Devuelve un ImportResult con created, updated, errors y filas preview.

Errores son por fila: `{row: int, message: str}`. Las filas con error nunca
se persisten; las válidas sí cuando dry_run=False.

Encoding y separador: intentamos detectar utf-8 con coma; el usuario puede
sobreescribir vía args.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnSpec:
    key: str
    label: str
    required: bool = False
    help: str = ""


@dataclass
class RowError:
    row: int
    message: str


@dataclass
class ImportResult:
    rows_total: int = 0
    rows_ok: int = 0
    rows_created: int = 0
    rows_updated: int = 0
    errors: list[RowError] = field(default_factory=list)
    preview: list[dict] = field(default_factory=list)

    @property
    def rows_error(self) -> int:
        return len(self.errors)


def parse_file(file_obj, filename: str) -> tuple[list[str], list[dict]]:
    """Devuelve (headers, rows-as-dict) de un archivo CSV o XLSX."""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return _parse_xlsx(file_obj)
    return _parse_csv(file_obj)


def _parse_csv(file_obj) -> tuple[list[str], list[dict]]:
    raw = file_obj.read()
    if isinstance(raw, bytes):
        # Intento utf-8 primero, después latin-1 (planillas exportadas de
        # Sheets/Excel en español a veces vienen en latin-1).
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    else:
        text = raw

    # Detectar delimitador.
    sample = text[:2000]
    delimiter = ","
    if sample.count(";") > sample.count(","):
        delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [dict(r) for r in reader]
    headers = reader.fieldnames or []
    return list(headers), rows


def _parse_xlsx(file_obj) -> tuple[list[str], list[dict]]:
    import openpyxl
    wb = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return [], []
    headers = [(h or "").strip() if isinstance(h, str) else str(h or "").strip() for h in header_row]
    rows: list[dict] = []
    for r in rows_iter:
        if all(c is None or c == "" for c in r):
            continue
        rows.append({headers[i]: r[i] if i < len(r) else None for i in range(len(headers))})
    return headers, rows


class BaseImporter:
    """Subclass declara `slug`, `label`, `columns` y override `process_row`.

    `process_row(row, dry_run)` debe devolver una de tres tuplas:
        ("created", obj_repr) | ("updated", obj_repr) | ("error", message)
    Para errores, lanzar ValueError(message) también funciona.
    """

    slug: str = ""
    label: str = ""
    description: str = ""
    columns: list[ColumnSpec] = []

    @classmethod
    def column_keys(cls) -> list[str]:
        return [c.key for c in cls.columns]

    @classmethod
    def required_keys(cls) -> list[str]:
        return [c.key for c in cls.columns if c.required]

    def process_row(self, row: dict, dry_run: bool) -> tuple[str, Any]:
        raise NotImplementedError

    def run(self, rows: list[dict], dry_run: bool = True) -> ImportResult:
        result = ImportResult(rows_total=len(rows))
        required = self.required_keys()
        for idx, row in enumerate(rows, start=2):  # row 2 = primera de datos (1 = header)
            # Validar columnas requeridas.
            missing = [k for k in required if not _value_truthy(row.get(k))]
            if missing:
                result.errors.append(RowError(
                    row=idx,
                    message=f"Falta(n) columna(s) obligatoria(s): {', '.join(missing)}",
                ))
                continue
            try:
                action, repr_ = self.process_row(row, dry_run)
                if action == "created":
                    result.rows_created += 1
                    result.rows_ok += 1
                elif action == "updated":
                    result.rows_updated += 1
                    result.rows_ok += 1
                else:  # "skipped" u otros
                    pass
                if len(result.preview) < 20:
                    result.preview.append({"row": idx, "action": action, "value": repr_})
            except (ValueError, ValidationError_compat) as exc:
                result.errors.append(RowError(row=idx, message=str(exc)))
        return result


def _value_truthy(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    return True


# Compat: aceptar Django ValidationError sin importarlo al top-level.
try:
    from django.core.exceptions import ValidationError as _DjangoVE
    ValidationError_compat = _DjangoVE
except Exception:  # pragma: no cover
    ValidationError_compat = ValueError
