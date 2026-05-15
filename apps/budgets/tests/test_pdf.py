"""PDF de presupuesto: smoke test del rendering del template."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string


def test_budget_pdf_template_renders(tenant) -> None:
    from apps.budgets.models import Budget, BudgetItem
    from apps.budgets.services import BudgetCalculatorService
    from apps.catalog.models import Material, Rubro, Unit
    from apps.companies.models import Company
    from apps.currencies.models import Currency
    from apps.pricing.models import Price
    from apps.projects.models import Project
    from apps.task_master.models import Task, TaskComponent

    company = Company.objects.create(name="PASFAS SA")
    project = Project.objects.create(name="Casa Demo", company=company)
    rubro = Rubro.objects.create(name="ESTRUCTURA")
    m2 = Unit.objects.create(name="m2", symbol="m2", category=Unit.Category.AREA)
    kg = Unit.objects.create(name="kg", symbol="kg", category=Unit.Category.WEIGHT)
    cemento = Material.objects.create(name="Cemento", rubro=rubro, unit=kg)
    ars = Currency.objects.get(code="ARS")

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

    budget = Budget.objects.create(
        project=project, currency=ars, margin_pct=Decimal("20"), name="P1 inicial",
    )
    BudgetItem.objects.create(budget=budget, task=task, quantity=Decimal("50"))

    totals = BudgetCalculatorService.compute(budget)
    items_view = [{
        "item": budget.items.first(),
        "unit_cost": Decimal("1000"),
        "total_cost": Decimal("50000"),
    }]

    html = render_to_string("budgets/pdf/budget.html", {
        "budget": budget,
        "totals": totals,
        "items_view": items_view,
        "today": date(2026, 5, 15),
    })

    assert "Casa Demo" in html
    assert "Revoque" in html
    assert "ARS" in html
    assert "Margen" in html
