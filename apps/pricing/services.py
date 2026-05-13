"""Servicios de cotización y de lookup de precios.

- CurrencyConversionService: conversión entre monedas usando ExchangeRateType,
  con soporte para tipos calculados (combinación ponderada tipo 70/30).
- PriceLookupService: precio "actual" de un item (Material, Subcontract, …)
  con estrategia configurable. Convierte a la moneda pedida usando el servicio
  de cotización.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import localdate

if TYPE_CHECKING:
    from apps.currencies.models import Currency

    from .models import ExchangeRate, ExchangeRateType, Price


class ExchangeRateNotFoundError(Exception):
    """No se encontró una cotización aplicable."""


class PriceNotFoundError(Exception):
    """No hay precios de referencia para el item solicitado."""


@dataclass
class ConversionResult:
    amount: Decimal
    rate_used: "ExchangeRate | None"
    rate_date: _date
    computed: bool = False  # True si la tasa fue calculada (no provino de un ExchangeRate stored)


# ---------------------------------------------------------------------------
# Conversión de moneda
# ---------------------------------------------------------------------------

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

        Para tipos calculados (weighted_combination), persiste el resultado
        como un ExchangeRate con source='calculated'. Así futuras consultas
        a la misma fecha leen lo cacheado y los recálculos no se disparan
        en cada acceso.
        """
        from .models import ExchangeRate, ExchangeRateType

        if date is None:
            date = localdate()

        existing = ExchangeRate.objects.filter(rate_type=rate_type, date=date).first()
        if existing is not None:
            return existing

        # Tipo calculado: armar la tasa a partir de sus componentes.
        if rate_type.calculation_type == ExchangeRateType.CalculationType.WEIGHTED:
            computed_rate = cls._compute_weighted_rate(rate_type, date, fallback_days)
            return ExchangeRate.objects.create(
                rate_type=rate_type,
                date=date,
                rate=computed_rate,
                source=ExchangeRate.Source.CALCULATED,
            )

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
    def _compute_weighted_rate(
        cls,
        rate_type: "ExchangeRateType",
        date: _date,
        fallback_days: int,
    ) -> Decimal:
        """Resuelve una cotización ponderada del estilo {"BNA": 0.7, "CCL": 0.3}."""
        from .models import ExchangeRateType

        formula = rate_type.combination_formula or {}
        if not isinstance(formula, dict) or not formula:
            raise ExchangeRateNotFoundError(
                f"El tipo {rate_type.name} es calculado pero no tiene fórmula."
            )

        total_weight = sum(Decimal(str(w)) for w in formula.values())
        if total_weight == 0:
            raise ExchangeRateNotFoundError(
                f"La fórmula de {rate_type.name} tiene pesos que suman cero."
            )

        components = ExchangeRateType.objects.filter(name__in=formula.keys()).in_bulk(field_name="name")

        missing = set(formula.keys()) - set(components.keys())
        if missing:
            raise ExchangeRateNotFoundError(
                f"Faltan tipos referenciados por {rate_type.name}: {sorted(missing)}."
            )

        # Cada componente debe ser del mismo par. Sino la combinación no tiene sentido.
        for comp in components.values():
            if comp.currency_from_id != rate_type.currency_from_id or comp.currency_to_id != rate_type.currency_to_id:
                raise ExchangeRateNotFoundError(
                    f"El tipo {comp.name} no coincide en par con {rate_type.name}."
                )

        weighted_sum = Decimal("0")
        for name, weight in formula.items():
            comp = components[name]
            comp_rate = cls.get_rate(comp, date=date, fallback_days=fallback_days)
            weighted_sum += comp_rate.rate * Decimal(str(weight))

        return (weighted_sum / total_weight).quantize(Decimal("0.0001"))

    @classmethod
    def convert(
        cls,
        amount: Decimal | float | int,
        from_currency: "Currency",
        to_currency: "Currency",
        date: _date | None = None,
        rate_type: "ExchangeRateType | None" = None,
    ) -> ConversionResult:
        """Convierte `amount` de `from_currency` a `to_currency`."""
        from .models import ExchangeRateType

        amount = Decimal(amount)

        if from_currency.pk == to_currency.pk:
            return ConversionResult(amount=amount, rate_used=None, rate_date=date or localdate())

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
        if rate_type.currency_from_id == from_currency.pk and rate_type.currency_to_id == to_currency.pk:
            converted = amount * rate.rate
        elif rate_type.currency_from_id == to_currency.pk and rate_type.currency_to_id == from_currency.pk:
            if rate.rate == 0:
                raise ExchangeRateNotFoundError(f"Cotización en cero para {rate_type.name} @ {rate.date}.")
            converted = amount / rate.rate
        else:
            raise ExchangeRateNotFoundError(
                f"El tipo {rate_type.name} no aplica al par {from_currency.code}/{to_currency.code}."
            )
        return ConversionResult(
            amount=converted,
            rate_used=rate,
            rate_date=rate.date,
            computed=rate.source == "calculated",
        )


def models_q_for_pair(a, b):
    from django.db.models import Q
    return Q(currency_from=a, currency_to=b) | Q(currency_from=b, currency_to=a)


# ---------------------------------------------------------------------------
# Lookup de precios
# ---------------------------------------------------------------------------

@dataclass
class PriceLookupResult:
    amount: Decimal
    currency: "Currency"
    effective_date: _date
    source: str
    converted: bool = False  # True si tuvimos que convertir de otra moneda


class PriceLookupService:
    """Resuelve el "precio actual" de un item del catálogo.

    Estrategias:
    - `most_recent` (default): toma el Price más reciente con is_reference=True
      cuya effective_date sea ≤ `date`. Si está en otra moneda, lo convierte.
    - `weighted_average_n_days`: promedio ponderado por cantidad de los últimos
      N días. Útil para suavizar oscilaciones cortas. (n_days configurable)
    - `min_n_days`: el mínimo de los últimos N días. Estrategia conservadora
      para presupuestos defensivos.

    Si más adelante se agrega un modelo OrganizationSettings, la estrategia
    default se lee de ahí.
    """

    STRATEGY_MOST_RECENT = "most_recent"
    STRATEGY_WEIGHTED_AVG = "weighted_average_n_days"
    STRATEGY_MIN = "min_n_days"

    @classmethod
    def get_current_price(
        cls,
        item,
        currency: "Currency | None" = None,
        date: _date | None = None,
        rate_type: "ExchangeRateType | None" = None,
        strategy: str = STRATEGY_MOST_RECENT,
        n_days: int = 30,
    ) -> PriceLookupResult:
        from .models import Price

        if date is None:
            date = localdate()

        ct = ContentType.objects.get_for_model(item)
        qs = Price.objects.filter(
            content_type=ct,
            object_id=item.pk,
            is_reference=True,
            effective_date__lte=date,
        )

        if strategy == cls.STRATEGY_MOST_RECENT:
            price = qs.order_by("-effective_date", "-created_at").first()
            if price is None:
                raise PriceNotFoundError(f"Sin precio de referencia para {item}.")
            result = cls._materialize(price, currency, date, rate_type)
            return result

        # Para weighted_avg y min, agrupar en ventana de N días.
        start = date - timedelta(days=n_days)
        window_qs = qs.filter(effective_date__gte=start)
        if not window_qs.exists():
            # Si nada en la ventana, caer en el más reciente disponible.
            return cls.get_current_price(
                item, currency=currency, date=date, rate_type=rate_type,
                strategy=cls.STRATEGY_MOST_RECENT,
            )

        # Normalizar todos los precios a la moneda pedida (o ARS si no se pidió).
        target = currency or _default_currency()
        normalized: list[tuple[Decimal, _date]] = []
        for p in window_qs:
            if p.currency_id == target.pk:
                normalized.append((p.amount, p.effective_date))
            else:
                conv = CurrencyConversionService.convert(
                    p.amount, p.currency, target, date=p.effective_date, rate_type=rate_type,
                )
                normalized.append((conv.amount, p.effective_date))

        if strategy == cls.STRATEGY_WEIGHTED_AVG:
            # Peso = 1 / (days_ago + 1) — los más recientes pesan más.
            num = Decimal("0")
            den = Decimal("0")
            for amount, eff_date in normalized:
                weight = Decimal(1) / Decimal((date - eff_date).days + 1)
                num += amount * weight
                den += weight
            return PriceLookupResult(
                amount=(num / den).quantize(Decimal("0.0001")),
                currency=target,
                effective_date=date,
                source="weighted_avg",
                converted=True,
            )

        if strategy == cls.STRATEGY_MIN:
            amount, eff_date = min(normalized, key=lambda t: t[0])
            return PriceLookupResult(
                amount=amount,
                currency=target,
                effective_date=eff_date,
                source="min",
                converted=target.pk != qs.first().currency_id,
            )

        raise ValueError(f"Estrategia desconocida: {strategy}")

    @classmethod
    def _materialize(
        cls,
        price: "Price",
        target_currency: "Currency | None",
        as_of_date: _date,
        rate_type: "ExchangeRateType | None",
    ) -> PriceLookupResult:
        if target_currency is None or target_currency.pk == price.currency_id:
            return PriceLookupResult(
                amount=price.amount,
                currency=price.currency,
                effective_date=price.effective_date,
                source=price.source,
            )
        conv = CurrencyConversionService.convert(
            price.amount, price.currency, target_currency,
            date=as_of_date, rate_type=rate_type,
        )
        return PriceLookupResult(
            amount=conv.amount,
            currency=target_currency,
            effective_date=price.effective_date,
            source=price.source,
            converted=True,
        )


def _default_currency():
    """ARS por defecto. Cuando exista OrganizationSettings, se leerá desde ahí."""
    from apps.currencies.models import Currency
    return Currency.objects.get(code="ARS")
