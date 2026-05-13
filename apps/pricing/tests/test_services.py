from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.currencies.models import Currency
from apps.pricing.models import ExchangeRate, ExchangeRateType
from apps.pricing.services import (
    CurrencyConversionService,
    ExchangeRateNotFoundError,
)


def _setup(tenant):
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    bna = ExchangeRateType.objects.create(
        name="BNA", currency_from=usd, currency_to=ars, is_default=True,
    )
    return usd, ars, bna


def test_get_rate_finds_exact_date(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    r = CurrencyConversionService.get_rate(bna, date(2026, 5, 13))
    assert r.rate == Decimal("1200")


def test_get_rate_falls_back_to_previous(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 10), rate=Decimal("1100"))
    r = CurrencyConversionService.get_rate(bna, date(2026, 5, 13))
    assert r.rate == Decimal("1100")
    assert r.date == date(2026, 5, 10)


def test_get_rate_raises_if_too_far_back(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2024, 1, 1), rate=Decimal("100"))
    with pytest.raises(ExchangeRateNotFoundError):
        CurrencyConversionService.get_rate(bna, date(2026, 5, 13))


def test_convert_usd_to_ars_multiplies(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    res = CurrencyConversionService.convert(Decimal("100"), usd, ars, date(2026, 5, 13))
    assert res.amount == Decimal("120000")


def test_convert_ars_to_usd_divides(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    res = CurrencyConversionService.convert(Decimal("120000"), ars, usd, date(2026, 5, 13))
    assert res.amount == Decimal("100")


def test_convert_same_currency_passthrough(tenant) -> None:
    usd, ars, _ = _setup(tenant)
    res = CurrencyConversionService.convert(Decimal("999"), usd, usd, date(2026, 5, 13))
    assert res.amount == Decimal("999")


def test_convert_picks_default_when_no_rate_type_given(tenant) -> None:
    usd, ars, bna = _setup(tenant)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    res = CurrencyConversionService.convert(Decimal("1"), usd, ars, date(2026, 5, 13))
    assert res.rate_used.rate_type_id == bna.pk


def test_convert_raises_without_default_type(tenant) -> None:
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    # No creamos ningún ExchangeRateType default.
    with pytest.raises(ExchangeRateNotFoundError):
        CurrencyConversionService.convert(Decimal("1"), usd, ars, date(2026, 5, 13))
