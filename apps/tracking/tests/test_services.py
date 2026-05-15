"""TrackingService.snapshot_project + VarianceAnalyzer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.budgets.models import Budget, BudgetItem
from apps.budgets.services import BudgetApprovalService
from apps.catalog.models import Material, Rubro, Supplier, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.pricing.models import Price
from apps.procurement.models import Purchase, PurchaseItem
from apps.projects.models import Project
from apps.task_master.models import Task, TaskAdjustmentSuggestion, TaskComponent
from apps.tracking.models import ProjectExecutionSnapshot, TaskExecution
from apps.tracking.services import (
    TrackingService,
    VarianceAnalyzer,
    approve_suggestion,
    reject_suggestion,
)


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    supplier = Supplier.objects.create(name="CORRALON")
    ars = Currency.objects.get(code="ARS")
    project = Project.objects.create(name="Casa Demo", company=company)

    ct = ContentType.objects.get_for_model(Material)
    Price.objects.create(
        content_type=ct, object_id=cemento.pk,
        amount=Decimal("100"), currency=ars,
        effective_date=date(2026, 5, 1),
        source=Price.Source.MANUAL, is_reference=True,
    )
    task = Task.objects.create(name="Revoque", rubro=rubro, output_unit=m2)
    TaskComponent.objects.create(
        task=task, source_type=TaskComponent.SourceType.MATERIAL,
        material=cemento, quantity_per_unit=Decimal("10"), input_unit=kg,
    )
    return company, rubro, m2, kg, cemento, supplier, ars, project, task


def test_snapshot_with_no_data(tenant) -> None:
    _, _, _, _, _, _, _, project, _ = _setup(tenant)
    result = TrackingService.snapshot_project(project, snapshot_date=date(2026, 5, 13))
    assert result.total_cost == Decimal("0")
    assert ProjectExecutionSnapshot.objects.filter(project=project).count() == 1


def test_snapshot_aggregates_purchases(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)

    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        amount_without_tax=Decimal("5000"),
        total_amount=Decimal("5000"),
    )
    PurchaseItem.objects.create(
        purchase=purchase, material=cemento,
        quantity=Decimal("50"), unit=kg, unit_price=Decimal("100"),
        task_id=task.pk,
    )

    result = TrackingService.snapshot_project(project, snapshot_date=date(2026, 5, 13))
    assert result.total_materials > 0
    assert result.total_cost > 0

    # TaskExecution debe haberse creado para la task con actual_cost > 0.
    te = TaskExecution.objects.get(project=project, task=task)
    assert te.actual_cost > 0


def test_snapshot_updates_existing_for_same_date(tenant) -> None:
    _, _, _, _, _, _, _, project, _ = _setup(tenant)
    TrackingService.snapshot_project(project, snapshot_date=date(2026, 5, 13))
    TrackingService.snapshot_project(project, snapshot_date=date(2026, 5, 13))
    assert ProjectExecutionSnapshot.objects.filter(project=project, snapshot_date=date(2026, 5, 13)).count() == 1


def test_task_execution_with_planned_from_approved_budget(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    from apps.accounts.models import User
    user = User.objects.create_user(email="appr@demo.com", password="ContraseñaLarga123")

    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("10"))
    BudgetApprovalService.approve(b, user)

    TrackingService.snapshot_project(project, snapshot_date=date(2026, 5, 13))
    te = TaskExecution.objects.get(project=project, task=task)
    assert te.planned_quantity == Decimal("10.0000")
    assert te.planned_cost > 0


def test_variance_analyzer_creates_suggestion_for_sustained_variance(tenant) -> None:
    """3 obras con la misma task y varianza alta → debería crear sugerencia."""
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    # Crear 3 projects con TaskExecution con varianza alta.
    company = Company.objects.get(name="PASFAS SA")
    for i in range(3):
        proj = Project.objects.create(name=f"Obra {i}", company=company)
        TaskExecution.objects.create(
            project=proj, task=task,
            planned_quantity=Decimal("1"), actual_quantity=Decimal("1.3"),
            planned_cost=Decimal("1000"), actual_cost=Decimal("1300"),
        )

    findings = VarianceAnalyzer.scan(threshold_pct=Decimal("15"), min_samples=3)
    assert len(findings) == 1
    assert findings[0].task_id == task.pk
    assert findings[0].sample_size == 3
    assert findings[0].avg_variance_pct > 0

    # Sugerencia creada
    sug = TaskAdjustmentSuggestion.objects.get(task=task, status=TaskAdjustmentSuggestion.Status.PENDING)
    assert sug.sample_size == 3


def test_variance_analyzer_ignores_low_variance(tenant) -> None:
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    company = Company.objects.get(name="PASFAS SA")
    for i in range(5):
        proj = Project.objects.create(name=f"Obra {i}", company=company)
        TaskExecution.objects.create(
            project=proj, task=task,
            planned_quantity=Decimal("1"), actual_quantity=Decimal("1.01"),
            planned_cost=Decimal("1000"), actual_cost=Decimal("1010"),
        )
    findings = VarianceAnalyzer.scan(threshold_pct=Decimal("15"))
    assert findings == []


def test_variance_analyzer_requires_min_samples(tenant) -> None:
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    company = Company.objects.get(name="PASFAS SA")
    proj = Project.objects.create(name="Obra Solo", company=company)
    TaskExecution.objects.create(
        project=proj, task=task,
        planned_quantity=Decimal("1"), actual_quantity=Decimal("2"),
        planned_cost=Decimal("1000"), actual_cost=Decimal("2000"),
    )
    findings = VarianceAnalyzer.scan(min_samples=3)
    assert findings == []


def test_approve_suggestion_increments_task_version(tenant) -> None:
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    from apps.accounts.models import User
    user = User.objects.create_user(email="rev@demo.com", password="ContraseñaLarga123")
    initial = task.version

    s = TaskAdjustmentSuggestion.objects.create(
        task=task, current_quantity=Decimal("1"),
        suggested_quantity=Decimal("1.2"), sample_size=3,
        variance_pct=Decimal("20"),
        status=TaskAdjustmentSuggestion.Status.PENDING,
    )
    approve_suggestion(s, user)
    s.refresh_from_db()
    task.refresh_from_db()
    assert s.status == TaskAdjustmentSuggestion.Status.APPROVED
    assert task.version == initial + 1


def test_reject_suggestion_keeps_task_version(tenant) -> None:
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    from apps.accounts.models import User
    user = User.objects.create_user(email="rej@demo.com", password="ContraseñaLarga123")
    initial = task.version

    s = TaskAdjustmentSuggestion.objects.create(
        task=task, current_quantity=Decimal("1"),
        suggested_quantity=Decimal("1.2"), sample_size=3,
        variance_pct=Decimal("20"),
        status=TaskAdjustmentSuggestion.Status.PENDING,
    )
    reject_suggestion(s, user)
    s.refresh_from_db()
    task.refresh_from_db()
    assert s.status == TaskAdjustmentSuggestion.Status.REJECTED
    assert task.version == initial


def test_cannot_approve_already_approved(tenant) -> None:
    _, _, _, _, _, _, _, _, task = _setup(tenant)
    from apps.accounts.models import User
    user = User.objects.create_user(email="dup@demo.com", password="ContraseñaLarga123")

    s = TaskAdjustmentSuggestion.objects.create(
        task=task, current_quantity=Decimal("1"),
        suggested_quantity=Decimal("1.2"), sample_size=3,
        variance_pct=Decimal("20"),
        status=TaskAdjustmentSuggestion.Status.APPROVED,
    )
    with pytest.raises(ValueError):
        approve_suggestion(s, user)
