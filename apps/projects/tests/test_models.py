from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import ProjectStatus
from apps.companies.models import Company
from apps.projects.models import Project


def test_project_str_is_name(tenant) -> None:
    c = Company.objects.create(name="PASFAS SA")
    p = Project.objects.create(name="Casa Magdalena", company=c)
    assert str(p) == "Casa Magdalena"


def test_project_unique_name_per_company(tenant) -> None:
    a = Company.objects.create(name="PASFAS SA")
    b = Company.objects.create(name="350 SRL")

    Project.objects.create(name="Casa Magdalena", company=a)
    # Mismo nombre en otra sociedad: OK.
    Project.objects.create(name="Casa Magdalena", company=b)

    # Pero no en la misma sociedad.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Project.objects.create(name="Casa Magdalena", company=a)


def test_project_code_unique_when_present(tenant) -> None:
    c = Company.objects.create(name="PASFAS SA")
    Project.objects.create(name="A", code="OB-001", company=c)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Project.objects.create(name="B", code="OB-001", company=c)


def test_project_allows_multiple_empty_codes(tenant) -> None:
    c = Company.objects.create(name="PASFAS SA")
    Project.objects.create(name="A", company=c)
    Project.objects.create(name="B", company=c)
    assert Project.objects.filter(company=c).count() == 2


def test_project_with_status(tenant) -> None:
    c = Company.objects.create(name="PASFAS SA")
    s = ProjectStatus.objects.create(name="En Construcción")
    p = Project.objects.create(name="Casa Test", company=c, status=s)
    assert p.status.name == "En Construcción"
