"""Tipos de cotización calculados (combinación ponderada estilo 70/30)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.currencies.models import Currency
from apps.pricing.models import ExchangeRate, ExchangeRateType
from apps.pricing.services import (
    CurrencyConversionService,
    ExchangeRateNotFoundError,
)


def _setup_components(tenant):
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    bna = ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    ccl = ExchangeRateType.objects.create(name="CCL", currency_from=usd, currency_to=ars)
    return usd, ars, bna, ccl


def test_weighted_rate_70_30(tenant) -> None:
    usd, ars, bna, ccl = _setup_components(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    ExchangeRate.objects.create(rate_type=ccl, date=date(2026, 5, 13), rate=Decimal("1500"))
    seventy_thirty = ExchangeRateType.objects.create(
        name="70/30", currency_from=usd, currency_to=ars,
        calculation_type=ExchangeRateType.CalculationType.WEIGHTED,
        combination_formula={"BNA": 0.7, "CCL": 0.3},
    )
    r = CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))
    # 1000*0.7 + 1500*0.3 = 700 + 450 = 1150
    assert r.rate == Decimal("1150.0000")
    assert r.source == ExchangeRate.Source.CALCULATED


def test_calculated_rate_is_cached_on_first_compute(tenant) -> None:
    usd, ars, bna, ccl = _setup_components(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    ExchangeRate.objects.create(rate_type=ccl, date=date(2026, 5, 13), rate=Decimal("1500"))
    seventy_thirty = ExchangeRateType.objects.create(
        name="70/30", currency_from=usd, currency_to=ars,
        calculation_type=ExchangeRateType.CalculationType.WEIGHTED,
        combination_formula={"BNA": 0.7, "CCL": 0.3},
    )
    r1 = CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))
    r2 = CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))
    # La segunda lectura devuelve el mismo registro (no recalcula).
    assert r1.pk == r2.pk


def test_weighted_rate_fails_if_component_missing_value(tenant) -> None:
    usd, ars, bna, ccl = _setup_components(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    # No cargamos CCL.
    seventy_thirty = ExchangeRateType.objects.create(
        name="70/30", currency_from=usd, currency_to=ars,
        calculation_type=ExchangeRateType.CalculationType.WEIGHTED,
        combination_formula={"BNA": 0.7, "CCL": 0.3},
    )
    with pytest.raises(ExchangeRateNotFoundError):
        CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))


def test_weighted_rate_fails_if_referenced_type_missing(tenant) -> None:
    usd, ars, bna, _ccl = _setup_components(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    seventy_thirty = ExchangeRateType.objects.create(
        name="70/30", currency_from=usd, currency_to=ars,
        calculation_type=ExchangeRateType.CalculationType.WEIGHTED,
        combination_formula={"BNA": 0.7, "INEXISTENTE": 0.3},
    )
    with pytest.raises(ExchangeRateNotFoundError):
        CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))


def test_weighted_rate_fails_if_pair_does_not_match(tenant) -> None:
    usd, ars, bna, _ccl = _setup_components(tenant)
    eur = Currency.objects.get(code="EUR")
    eur_ars = ExchangeRateType.objects.create(name="EUR-ARS", currency_from=eur, currency_to=ars)
    ExchangeRate.objects.create(rate_type=eur_ars, date=date(2026, 5, 13), rate=Decimal("1300"))
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1000"))
    seventy_thirty = ExchangeRateType.objects.create(
        name="MIX", currency_from=usd, currency_to=ars,
        calculation_type=ExchangeRateType.CalculationType.WEIGHTED,
        combination_formula={"BNA": 0.5, "EUR-ARS": 0.5},
    )
    with pytest.raises(ExchangeRateNotFoundError):
        CurrencyConversionService.get_rate(seventy_thirty, date(2026, 5, 13))
