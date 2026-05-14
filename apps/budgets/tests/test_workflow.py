"""Flujo de Budget: draft → submitted → approved + snapshot + supersedencia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models import User
from apps.catalog.models import Material, ProjectStatus, Rubro, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.pricing.models import Price
from apps.projects.models import Project
from apps.task_master.models import Task, TaskComponent
from apps.budgets.models import Budget, BudgetItem
from apps.budgets.services import (
    BudgetApprovalService,
    BudgetCalculatorService,
    BudgetSnapshotService,
)


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    ars = Currency.objects.get(code="ARS")

    # Seed price
    ct = ContentType.objects.get_for_model(Material)
    Price.objects.create(
        content_type=ct, object_id=cemento.pk,
        amount=Decimal("100"), currency=ars,
        effective_date=date(2026, 5, 1),
        source=Price.Source.MANUAL, is_reference=True,
    )

    project = Project.objects.create(name="Casa Demo", company=company)

    task = Task.objects.create(name="Revoque", rubro=rubro, output_unit=m2)
    TaskComponent.objects.create(
        task=task, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento, quantity_per_unit=Decimal("10"), input_unit=kg,
    )
    # task por m2: 10 × 100 = 1000.

    return company, project, task, ars


def test_budget_live_totals_in_draft(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars, margin_pct=Decimal("20"))
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("50"))
    # 50 m2 × 1000 = 50000 materials. Margen 20% → 60000.
    totals = BudgetCalculatorService.compute(b)
    assert totals.materials == Decimal("50000.00")
    assert totals.subtotal == Decimal("50000.00")
    assert totals.margin_amount == Decimal("10000.00")
    assert totals.total_with_margin == Decimal("60000.00")


def test_budget_freeze_snapshots_unit_cost(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars, margin_pct=Decimal("0"))
    item = BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("10"))
    BudgetSnapshotService.freeze(b, pricing_date=date(2026, 5, 13))
    item.refresh_from_db()
    b.refresh_from_db()
    assert item.unit_cost == Decimal("1000.0000")
    assert item.total_cost == Decimal("10000.00")
    assert b.pricing_date == date(2026, 5, 13)
    assert b.materials_cost == Decimal("10000.00")
    assert b.total_with_margin == Decimal("10000.00")
    # recipe_snapshot guarda los componentes serializados
    assert item.recipe_snapshot["item_label"] == "Revoque"
    assert len(item.recipe_snapshot["components"]) == 1


def test_submit_transitions_to_submitted_and_locks(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("5"))
    BudgetApprovalService.submit(b)
    b.refresh_from_db()
    assert b.status == Budget.Status.SUBMITTED
    assert b.is_locked
    assert b.materials_cost == Decimal("5000.00")


def test_approve_supersedes_previous_approved(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    user = User.objects.create_user(email="approver@demo.com", password="ContraseñaLarga123")

    p1 = Budget.objects.create(project=project, currency=ars, version=1)
    BudgetItem.objects.create(budget=p1, task=task, quantity=Decimal("1"))
    BudgetApprovalService.approve(p1, user)
    p1.refresh_from_db()
    assert p1.status == Budget.Status.APPROVED
    assert p1.approved_by == user

    p2 = Budget.objects.create(project=project, currency=ars, version=2)
    BudgetItem.objects.create(budget=p2, task=task, quantity=Decimal("2"))
    BudgetApprovalService.approve(p2, user)

    p1.refresh_from_db()
    p2.refresh_from_db()
    assert p1.status == Budget.Status.SUPERSEDED
    assert p2.status == Budget.Status.APPROVED


def test_clone_creates_next_version_with_same_items(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    user = User.objects.create_user(email="cloner@demo.com", password="ContraseñaLarga123")

    p1 = Budget.objects.create(project=project, currency=ars, name="Inicial", margin_pct=Decimal("15"))
    BudgetItem.objects.create(budget=p1, task=task, quantity=Decimal("7"), order=1)

    p2 = BudgetApprovalService.clone_as_new_version(p1, user)
    assert p2.version == 2
    assert p2.status == Budget.Status.DRAFT
    assert p2.margin_pct == Decimal("15")
    assert p2.items.count() == 1
    new_item = p2.items.first()
    assert new_item.task_id == task.pk
    assert new_item.quantity == Decimal("7")


def test_cannot_edit_locked_budget_via_service(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("1"))
    BudgetApprovalService.submit(b)
    b.refresh_from_db()
    with pytest.raises(ValueError):
        BudgetApprovalService.submit(b)


def test_locked_budget_reads_totals_from_snapshot(tenant) -> None:
    _, project, task, ars = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars, margin_pct=Decimal("10"))
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("3"))
    BudgetApprovalService.submit(b)
    b.refresh_from_db()

    # Cambiar precio post-freeze NO debe afectar.
    ct = ContentType.objects.get_for_model(Material)
    cemento = Material.objects.get(name="Cemento")
    Price.objects.create(
        content_type=ct, object_id=cemento.pk,
        amount=Decimal("9999"), currency=ars,
        effective_date=date(2026, 6, 1),
        source=Price.Source.MANUAL, is_reference=True,
    )
    totals = BudgetCalculatorService.compute(b)
    # 3 × 1000 = 3000 materials + 10% margen = 3300.
    assert totals.materials == Decimal("3000.00")
    assert totals.total_with_margin == Decimal("3300.00")
