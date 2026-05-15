"""Helper para generar PDFs con WeasyPrint.

Patrón de uso:
    return render_pdf(request, "budgets/pdf/budget.html", {...}, "presupuesto.pdf")
"""

from __future__ import annotations

from django.http import HttpResponse
from django.template.loader import render_to_string


def render_pdf(request, template_name: str, context: dict, filename: str, *, attachment: bool = False) -> HttpResponse:
    """Renderiza un template Django como PDF usando WeasyPrint.

    `attachment=True` fuerza descarga; sino se abre inline en el browser.
    """
    from weasyprint import HTML

    html_str = render_to_string(template_name, context, request=request)
    base_url = request.build_absolute_uri("/") if request else None
    pdf_bytes = HTML(string=html_str, base_url=base_url).write_pdf()

    disposition = "attachment" if attachment else "inline"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response
