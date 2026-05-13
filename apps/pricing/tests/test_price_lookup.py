"""PriceLookupService: resolución de precios actuales con estrategias."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.models import Rubro, Unit, Material
from apps.currencies.models import Currency
from apps.pricing.models import ExchangeRate, ExchangeRateType, Price
from apps.pricing.services import (
    PriceLookupService,
    PriceNotFoundError,
)


def _make_material(tenant):
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    unit = Unit.objects.create(name="Kilogramo", symbol="kg", category=Unit.Category.WEIGHT)
    return Material.objects.create(name="Cemento", rubro=rubro, unit=unit)


def _price(mat, amount, eff_date, currency_code="ARS", is_reference=True):
    return Price.objects.create(
        item=mat,
        amount=Decimal(str(amount)),
        currency=Currency.objects.get(code=currency_code),
        effective_date=eff_date,
        is_reference=is_reference,
    )


def test_most_recent_strategy_returns_latest_reference_price(tenant) -> None:
    mat = _make_material(tenant)
    _price(mat, 100, date(2026, 5, 1))
    _price(mat, 120, date(2026, 5, 10))
    _price(mat, 90, date(2026, 4, 1))

    res = PriceLookupService.get_current_price(mat, date=date(2026, 5, 13))
    assert res.amount == Decimal("120")


def test_most_recent_ignores_non_reference_prices(tenant) -> None:
    mat = _make_material(tenant)
    _price(mat, 100, date(2026, 5, 1))
    # Oferta puntual marcada como no-referencia: se ignora.
    _price(mat, 50, date(2026, 5, 10), is_reference=False)

    res = PriceLookupService.get_current_price(mat, date=date(2026, 5, 13))
    assert res.amount == Decimal("100")


def test_returns_error_if_no_prices(tenant) -> None:
    mat = _make_material(tenant)
    with pytest.raises(PriceNotFoundError):
        PriceLookupService.get_current_price(mat, date=date(2026, 5, 13))


def test_returns_error_if_only_future_prices(tenant) -> None:
    mat = _make_material(tenant)
    _price(mat, 100, date(2026, 6, 1))
    with pytest.raises(PriceNotFoundError):
        PriceLookupService.get_current_price(mat, date=date(2026, 5, 13))


def test_converts_to_target_currency(tenant) -> None:
    """Si el precio está en USD y pido en ARS, debe convertir usando el default."""
    mat = _make_material(tenant)
    usd = Currency.objects.get(code="USD")
    ars = Currency.objects.get(code="ARS")
    bna = ExchangeRateType.objects.create(
        name="BNA", currency_from=usd, currency_to=ars, is_default=True,
    )
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    _price(mat, 50, date(2026, 5, 13), currency_code="USD")

    res = PriceLookupService.get_current_price(mat, currency=ars, date=date(2026, 5, 13))
    assert res.amount == Decimal("60000")
    assert res.currency.code == "ARS"
    assert res.converted is True


def test_weighted_average_strategy(tenant) -> None:
    """El promedio ponderado pesa más a los precios recientes."""
    mat = _make_material(tenant)
    _price(mat, 100, date(2026, 5, 13))  # weight = 1/1
    _price(mat, 200, date(2026, 5, 12))  # weight = 1/2
    _price(mat, 300, date(2026, 5, 11))  # weight = 1/3

    res = PriceLookupService.get_current_price(
        mat, date=date(2026, 5, 13),
        strategy=PriceLookupService.STRATEGY_WEIGHTED_AVG, n_days=30,
    )
    # num = 100*1 + 200*0.5 + 300*0.3333... = 100 + 100 + 100 = 300
    # den = 1 + 0.5 + 0.3333... = 1.8333...
    # avg = 300 / 1.8333 ≈ 163.6364
    assert Decimal("163") < res.amount < Decimal("164")


def test_min_strategy(tenant) -> None:
    mat = _make_material(tenant)
    _price(mat, 100, date(2026, 5, 13))
    _price(mat, 80, date(2026, 5, 11))
    _price(mat, 120, date(2026, 5, 12))

    res = PriceLookupService.get_current_price(
        mat, date=date(2026, 5, 13),
        strategy=PriceLookupService.STRATEGY_MIN, n_days=30,
    )
    assert res.amount == Decimal("80")
