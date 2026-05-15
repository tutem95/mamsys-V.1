from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.timezone import localdate
from django.views.generic import CreateView, ListView, UpdateView

from apps.permissions.constants import VIEW_PRICING
from apps.permissions.decorators import PermissionRequiredMixin

from .forms import ExchangeRateForm, ExchangeRateTypeForm
from .models import ExchangeRate, ExchangeRateType


# ---------------------------------------------------------------------------
# ExchangeRateType (Tipos)
# ---------------------------------------------------------------------------

@method_decorator(login_required, name="dispatch")
class ExchangeRateTypeListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_PRICING
    model = ExchangeRateType
    template_name = "pricing/type_list.html"
    context_object_name = "rate_types"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("currency_from", "currency_to")
            .prefetch_related("rates")
        )


@method_decorator(login_required, name="dispatch")
class ExchangeRateTypeCreateView(CreateView):
    model = ExchangeRateType
    form_class = ExchangeRateTypeForm
    template_name = "pricing/type_form.html"
    success_url = reverse_lazy("pricing:type_list")


@method_decorator(login_required, name="dispatch")
class ExchangeRateTypeUpdateView(UpdateView):
    model = ExchangeRateType
    form_class = ExchangeRateTypeForm
    template_name = "pricing/type_form.html"

    def get_success_url(self):
        return reverse_lazy("pricing:type_detail", args=[self.object.pk])


@login_required
def type_detail(request, pk: int):
    """Detalle de un tipo: histórico de cotizaciones + form rápido para cargar la del día."""
    rate_type = get_object_or_404(
        ExchangeRateType.objects.select_related("currency_from", "currency_to"),
        pk=pk,
    )

    if request.method == "POST":
        form = ExchangeRateForm(request.POST)
        if form.is_valid():
            rate = form.save(commit=False)
            rate.rate_type = rate_type
            rate.created_by = request.user
            try:
                rate.save()
                messages.success(
                    request,
                    f"Cotización de {rate_type.name} para {rate.date}: {rate.rate}.",
                )
                return redirect("pricing:type_detail", pk=rate_type.pk)
            except Exception as exc:  # IntegrityError por ej. (rate_type, date) duplicado
                form.add_error(None, f"No se pudo guardar: {exc}")
    else:
        form = ExchangeRateForm(initial={"date": localdate()})

    rates = rate_type.rates.order_by("-date")[:60]
    return render(request, "pricing/type_detail.html", {
        "rate_type": rate_type,
        "rates": rates,
        "form": form,
    })
