"""La data migration siembra las 3 monedas de arranque."""

from __future__ import annotations

import pytest

from apps.currencies.models import Currency


@pytest.mark.django_db
def test_seed_creates_ars_usd_eur() -> None:
    codes = set(Currency.objects.values_list("code", flat=True))
    assert {"ARS", "USD", "EUR"}.issubset(codes)
