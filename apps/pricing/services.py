"""Servicios de conversión de moneda.

API mínima de Fase 3: conversión vía un ExchangeRateType. Los tipos calculados
(70/30 desde BNA+CCL) y el PriceLookupService se suman en la siguiente entrega.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils.timezone import localdate

if TYPE_CHECKING:
    from apps.currencies.models import Currency

    from .models import ExchangeRate, ExchangeRateType


class ExchangeRateNotFoundError(Exception):
    """No se encontró una cotización aplicable."""


@dataclass
class ConversionResult:
    amount: Decimal
    rate_used: "ExchangeRate"
    rate_date: _date


class CurrencyConversionService:
    """Convierte montos entre monedas usando cotizaciones cargadas por la org."""

    DEFAULT_FALLBACK_DAYS = 30

    @classmethod
    def get_rate(
        cls,
        rate_type: "ExchangeRateType",
        date: _date | None = None,
        fallback_to_previous: bool = True,
        fallback_days: int = DEFAULT_FALLBACK_DAYS,
    ) -> "ExchangeRate":
        """Devuelve la cotización aplicable.

        Si existe en `date`, la usa. Si no y `fallback_to_previous=True`, busca
        la más cercana anterior dentro de `fallback_days`. Si no hay → raise.
        """
        from .models import ExchangeRate

        if date is None:
            date = localdate()

        rate = ExchangeRate.objects.filter(rate_type=rate_type, date=date).first()
        if rate is not None:
            return rate

        if not fallback_to_previous:
            raise ExchangeRateNotFoundError(
                f"No hay cotización de {rate_type.name} para {date}."
            )

        earliest = date - timedelta(days=fallback_days)
        rate = (
            ExchangeRate.objects.filter(
                rate_type=rate_type,
                date__lt=date,
                date__gte=earliest,
            )
            .order_by("-date")
            .first()
        )
        if rate is None:
            raise ExchangeRateNotFoundError(
                f"No hay cotización de {rate_type.name} dentro de los últimos "
                f"{fallback_days} días previos a {date}. Cargá una manualmente."
            )
        return rate

    @classmethod
    def convert(
        cls,
        amount: Decimal | float | int,
        from_currency: "Currency",
        to_currency: "Currency",
        date: _date | None = None,
        rate_type: "ExchangeRateType | None" = None,
    ) -> ConversionResult:
        """Convierte `amount` de `from_currency` a `to_currency`.

        Si `rate_type` no se pasa, busca el ExchangeRateType marcado como
        default cuyo par de monedas coincida (en cualquier dirección).
        """
        from .models import ExchangeRateType

        amount = Decimal(amount)

        if from_currency.pk == to_currency.pk:
            # No hay cotización pero igual reportamos algo razonable.
            return ConversionResult(amount=amount, rate_used=None, rate_date=date or localdate())  # type: ignore[arg-type]

        if rate_type is None:
            rate_type = (
                ExchangeRateType.objects.filter(
                    active=True,
                    is_default=True,
                )
                .filter(
                    models_q_for_pair(from_currency, to_currency),
                )
                .first()
            )
            if rate_type is None:
                raise ExchangeRateNotFoundError(
                    "No hay un tipo de cotización default para el par "
                    f"{from_currency.code}/{to_currency.code}."
                )

        rate = cls.get_rate(rate_type, date=date)
        # rate_type.currency_from -> rate_type.currency_to con multiplicación.
        if rate_type.currency_from_id == from_currency.pk and rate_type.currency_to_id == to_currency.pk:
            converted = amount * rate.rate
        elif rate_type.currency_from_id == to_currency.pk and rate_type.currency_to_id == from_currency.pk:
            # Conversión inversa: dividir.
            if rate.rate == 0:
                raise ExchangeRateNotFoundError(f"Cotización en cero para {rate_type.name} @ {rate.date}.")
            converted = amount / rate.rate
        else:
            raise ExchangeRateNotFoundError(
                f"El tipo de cotización {rate_type.name} no aplica al par "
                f"{from_currency.code}/{to_currency.code}."
            )
        return ConversionResult(amount=converted, rate_used=rate, rate_date=rate.date)


def models_q_for_pair(a, b):
    """Devuelve un Q para encontrar ExchangeRateType cuyo par coincida en cualquier orden."""
    from django.db.models import Q
    return Q(currency_from=a, currency_to=b) | Q(currency_from=b, currency_to=a)
