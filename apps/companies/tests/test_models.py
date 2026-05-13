from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.companies.models import Company


def test_company_defaults_to_responsable_inscripto(tenant) -> None:
    c = Company.objects.create(name="Test SA")
    assert c.iva_condition == Company.IVACondition.RESPONSABLE_INSCRIPTO
    assert c.active is True


def test_company_tax_id_unique_when_present(tenant) -> None:
    Company.objects.create(name="A", tax_id="30-12345678-9")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Company.objects.create(name="B", tax_id="30-12345678-9")


def test_company_allows_multiple_empty_tax_ids(tenant) -> None:
    """El unique parcial permite varias sociedades sin CUIT cargado."""
    Company.objects.create(name="A")
    Company.objects.create(name="B")
    assert Company.objects.count() == 2
