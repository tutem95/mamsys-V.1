from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .base import parse_file
from .importers import IMPORTERS, get_importer
from .models import ImportLog


@login_required
def index(request):
    """Lista de importadores disponibles."""
    importers = [
        {
            "slug": cls.slug,
            "label": cls.label,
            "description": cls.description,
            "columns": cls.columns,
        }
        for cls in IMPORTERS.values()
    ]
    return render(request, "imports/index.html", {"importers": importers})


@login_required
def upload(request, slug: str):
    """Sube un CSV/XLSX, parsea y muestra preview (dry-run).

    El form pasa los headers + rows (JSON) al confirm view para no re-parsear.
    """
    importer = get_importer(slug)
    if importer is None:
        messages.error(request, "Importador desconocido.")
        return redirect("imports:index")

    if request.method != "POST":
        return render(request, "imports/upload.html", {"importer": importer.__class__})

    f = request.FILES.get("file")
    if f is None:
        messages.error(request, "Subí un archivo CSV o XLSX.")
        return render(request, "imports/upload.html", {"importer": importer.__class__})

    try:
        headers, rows = parse_file(f, f.name)
    except Exception as exc:
        messages.error(request, f"No se pudo leer el archivo: {exc}")
        return render(request, "imports/upload.html", {"importer": importer.__class__})

    if not rows:
        messages.warning(request, "El archivo está vacío.")
        return render(request, "imports/upload.html", {"importer": importer.__class__})

    # Validar que tenga al menos las columnas requeridas.
    required = importer.required_keys()
    missing_cols = [k for k in required if k not in headers]
    if missing_cols:
        messages.error(
            request,
            f"Faltan columnas en el archivo: {', '.join(missing_cols)}. "
            f"Esperadas: {', '.join(importer.column_keys())}.",
        )
        return render(request, "imports/upload.html", {"importer": importer.__class__, "headers": headers})

    result = importer.run(rows, dry_run=True)

    # Guardar las rows en sesión para la confirmación. JSON serializable.
    request.session[f"imports:{slug}:rows"] = json.dumps(rows, default=str)
    request.session[f"imports:{slug}:filename"] = f.name

    return render(request, "imports/preview.html", {
        "importer": importer.__class__,
        "headers": headers,
        "result": result,
        "filename": f.name,
        "rows_count": len(rows),
    })


@login_required
def confirm(request, slug: str):
    """Confirma la importación leyendo las rows de la sesión."""
    importer = get_importer(slug)
    if importer is None:
        messages.error(request, "Importador desconocido.")
        return redirect("imports:index")
    if request.method != "POST":
        return redirect("imports:upload", slug=slug)

    rows_raw = request.session.get(f"imports:{slug}:rows")
    filename = request.session.get(f"imports:{slug}:filename", "")
    if not rows_raw:
        messages.error(request, "Sesión expirada o sin datos en preview. Volvé a subir el archivo.")
        return redirect("imports:upload", slug=slug)

    rows = json.loads(rows_raw)
    result = importer.run(rows, dry_run=False)

    log = ImportLog.objects.create(
        importer_slug=slug,
        importer_label=importer.label,
        filename=filename,
        status=ImportLog.Status.COMMITTED if result.rows_error == 0 else ImportLog.Status.FAILED,
        rows_total=result.rows_total,
        rows_ok=result.rows_ok,
        rows_created=result.rows_created,
        rows_updated=result.rows_updated,
        rows_error=result.rows_error,
        errors=[{"row": e.row, "message": e.message} for e in result.errors],
        summary=(
            f"{result.rows_created} creado(s), {result.rows_updated} actualizado(s), "
            f"{result.rows_error} con error sobre {result.rows_total} filas."
        ),
        user=request.user,
        created_by=request.user,
        updated_by=request.user,
    )

    # Limpiar sesión.
    request.session.pop(f"imports:{slug}:rows", None)
    request.session.pop(f"imports:{slug}:filename", None)

    if result.rows_error == 0:
        messages.success(request, f"Importación OK: {result.rows_created} creados, {result.rows_updated} actualizados.")
    else:
        messages.warning(
            request,
            f"Importación con errores: {result.rows_error} fila(s) fallaron. "
            f"{result.rows_ok} se guardaron OK.",
        )
    return redirect("imports:log_detail", pk=log.pk)


@method_decorator(login_required, name="dispatch")
class LogListView(ListView):
    model = ImportLog
    template_name = "imports/log_list.html"
    paginate_by = 50
    context_object_name = "logs"


@login_required
def log_detail(request, pk: int):
    log = ImportLog.objects.get(pk=pk)
    return render(request, "imports/log_detail.html", {"log": log})
