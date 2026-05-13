from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.currencies.models import Currency
from apps.pricing.models import ExchangeRate, ExchangeRateType


def _pair():
    return Currency.objects.get(code="USD"), Currency.objects.get(code="ARS")


def test_rate_type_unique_name(tenant) -> None:
    usd, ars = _pair()
    ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)


def test_rate_unique_per_type_per_date(tenant) -> None:
    usd, ars = _pair()
    bna = ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1250"))


def test_rate_to_amount_multiplies(tenant) -> None:
    usd, ars = _pair()
    bna = ExchangeRateType.objects.create(name="BNA", currency_from=usd, currency_to=ars)
    r = ExchangeRate.objects.create(rate_type=bna, date=date(2026, 5, 13), rate=Decimal("1200"))
    assert r.to_amount(Decimal("100")) == Decimal("120000")
