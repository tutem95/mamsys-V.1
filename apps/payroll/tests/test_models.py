from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import EmployeeStatus, Position, Team
from apps.companies.models import Company
from apps.payroll.models import (
    EmergencyContact,
    Employee,
    EmployeeBanking,
    EmployeePersonalData,
)


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    position = Position.objects.create(name="Oficial")
    status = EmployeeStatus.objects.create(name="Activo")
    return company, position, status


def test_str_uses_personal_data_full_name_when_available(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    EmployeePersonalData.objects.create(
        employee=emp, first_name="Juan", last_name="Pérez",
    )
    assert str(emp) == "Juan Pérez"


def test_str_falls_back_when_no_personal_data(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company, internal_id="E-007")
    assert "E-007" in str(emp)


def test_internal_id_unique_per_company_when_present(tenant) -> None:
    a = Company.objects.create(name="A")
    b = Company.objects.create(name="B")
    Employee.objects.create(company=a, internal_id="E-001")
    # Mismo ID en otra sociedad: OK.
    Employee.objects.create(company=b, internal_id="E-001")
    # Pero no en la misma.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Employee.objects.create(company=a, internal_id="E-001")


def test_internal_id_can_be_empty_repeated(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    Employee.objects.create(company=company)
    Employee.objects.create(company=company)
    assert Employee.objects.count() == 2


def test_employee_can_join_multiple_teams(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    t1 = Team.objects.create(name="Equipo Adan")
    t2 = Team.objects.create(name="Equipo Naty")
    emp.teams.add(t1, t2)
    assert emp.teams.count() == 2


def test_personal_data_age_is_computed_from_birth_date(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    pd = EmployeePersonalData.objects.create(
        employee=emp, first_name="X", last_name="Y", birth_date=date(2000, 1, 1),
    )
    age = pd.age
    assert age is not None and 24 <= age <= 30  # rango razonable según hoy


def test_personal_data_age_is_none_without_birth_date(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    pd = EmployeePersonalData.objects.create(employee=emp, first_name="X", last_name="Y")
    assert pd.age is None


def test_banking_one_to_one(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    EmployeeBanking.objects.create(employee=emp, cbu="1234567890123456789012")
    # No se puede crear otro Banking para el mismo Employee.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeeBanking.objects.create(employee=emp, cbu="9999999999999999999999")


def test_emergency_contacts_one_to_many(tenant) -> None:
    company, _pos, _status = _setup(tenant)
    emp = Employee.objects.create(company=company)
    EmergencyContact.objects.create(employee=emp, full_name="Madre", phone="11-1111-1111")
    EmergencyContact.objects.create(employee=emp, full_name="Padre", phone="11-2222-2222")
    assert emp.emergency_contacts.count() == 2
