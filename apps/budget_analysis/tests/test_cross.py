"""BudgetActualCrossService: cruce de un Budget snapshotado contra compras y nómina reales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from apps.budget_analysis.services import BudgetActualCrossService, serialize_result
from apps.budgets.models import Budget, BudgetItem
from apps.budgets.services import BudgetApprovalService
from apps.catalog.models import Material, Position, ProjectStatus, Rubro, Supplier, Unit
from apps.companies.models import Company
from apps.currencies.models import Currency
from apps.pricing.models import Price
from apps.procurement.models import Purchase, PurchaseItem
from apps.projects.models import Project
from apps.task_master.models import Task, TaskComponent


def _setup(tenant):
    company = Company.objects.create(name="PASFAS SA")
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    supplier = Supplier.objects.create(name="CORRALON")
    ars = Currency.objects.get(code="ARS")
    project = Project.objects.create(name="Casa Demo", company=company)

    # Seed price y task
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


def test_cross_with_no_actual_shows_only_planned(tenant) -> None:
    _, _, _, _, _, _, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("10"))
    BudgetApprovalService.submit(b)
    b.refresh_from_db()

    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    assert result.materials.planned == Decimal("10000.00")
    assert result.materials.actual == Decimal("0")
    assert result.total_planned == Decimal("10000.00")
    assert result.total_actual == Decimal("0.00")
    assert result.variance_amount == Decimal("-10000.00")
    assert result.purchases_count == 0


def test_cross_with_purchase_in_same_rubro(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("10"))
    BudgetApprovalService.submit(b)

    # Compra real con 1 ítem de cemento por $5000 sin IVA, total $6050.
    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        amount_without_tax=Decimal("5000"),
        iva_21=Decimal("1050"),
        total_amount=Decimal("6050"),
    )
    PurchaseItem.objects.create(
        purchase=purchase, material=cemento,
        quantity=Decimal("50"), unit=kg, unit_price=Decimal("100"),
    )

    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    # Materials: planned 10000, actual ≈ 6050 (total con IVA, prorrateado al ítem).
    assert result.materials.planned == Decimal("10000.00")
    assert abs(result.materials.actual - Decimal("6050")) < Decimal("0.01")
    assert result.purchases_count == 1


def test_cutoff_date_excludes_later_purchases(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("1"))
    BudgetApprovalService.submit(b)

    Purchase.objects.create(
        invoice_date=date(2026, 5, 15),  # después del cutoff
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        amount_without_tax=Decimal("9999"),
        total_amount=Decimal("9999"),
    )
    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 10), currency=ars)
    assert result.materials.actual == Decimal("0")
    assert result.purchases_count == 0


def test_cancelled_purchases_excluded(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("1"))
    BudgetApprovalService.submit(b)

    Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.CANCELLED,
        project=project,
        total_amount=Decimal("5000"),
    )
    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    assert result.purchases_count == 0
    assert result.materials.actual == Decimal("0")


def test_subcontract_purchase_goes_to_subcontracts_bucket(tenant) -> None:
    from apps.catalog.models import Subcontract
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    sub_unit = Unit.objects.create(name="uni", symbol="UNI", category=Unit.Category.OTHER)
    sub = Subcontract.objects.create(name="Estudio Suelo", unit=sub_unit)

    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("1"))
    BudgetApprovalService.submit(b)

    purchase = Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        is_subcontract=True,
        project=project,
        amount_without_tax=Decimal("3000"),
        total_amount=Decimal("3000"),
    )
    PurchaseItem.objects.create(
        purchase=purchase, subcontract=sub,
        quantity=Decimal("1"), unit=sub_unit, unit_price=Decimal("3000"),
    )
    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    assert result.subcontracts.actual > 0
    assert result.materials.actual == Decimal("0")


def test_variance_positive_when_actual_exceeds_planned(tenant) -> None:
    company, rubro, m2, kg, cemento, supplier, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("1"))  # planned 1000
    BudgetApprovalService.submit(b)

    Purchase.objects.create(
        invoice_date=date(2026, 5, 10),
        supplier=supplier, company=company, rubro=rubro,
        original_currency=ars,
        purchase_type=Purchase.PurchaseType.OBRA,
        status=Purchase.Status.TO_PAY,
        project=project,
        amount_without_tax=Decimal("5000"),
        total_amount=Decimal("5000"),
    )
    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    assert result.variance_amount > 0  # gastamos más
    assert result.variance_pct > 0


def test_serialize_result_to_dict(tenant) -> None:
    _, _, _, _, _, _, ars, project, task = _setup(tenant)
    b = Budget.objects.create(project=project, currency=ars)
    BudgetItem.objects.create(budget=b, task=task, quantity=Decimal("2"))
    BudgetApprovalService.submit(b)

    result = BudgetActualCrossService.compute(b, cutoff_date=date(2026, 5, 13), currency=ars)
    data = serialize_result(result)
    assert data["project_name"] == "Casa Demo"
    assert data["currency_code"] == "ARS"
    assert "materials" in data and "labor" in data and "subcontracts" in data
    assert isinstance(data["rubros"], list)
    assert isinstance(data["tasks"], list)
