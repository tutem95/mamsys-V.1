"""Servicios de presupuesto.

- BudgetCalculatorService: para budgets en draft, calcula al vuelo usando
  TaskCostCalculator. Para budgets ya snapshotados, lee los campos
  congelados sin recalcular.
- BudgetSnapshotService: congela los campos al pasar de draft → submitted.
- BudgetApprovalService: cuando se aprueba una version, marca la anterior
  aprobada del mismo proyecto como superseded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils.timezone import localdate, now as tz_now

if TYPE_CHECKING:
    from .models import Budget, BudgetItem


@dataclass
class BudgetTotals:
    materials: Decimal
    labor: Decimal
    subcontracts: Decimal
    subtotal: Decimal
    margin_amount: Decimal
    total_with_margin: Decimal


class BudgetCalculatorService:
    """Totales del presupuesto.

    En `draft`: usa TaskCostCalculator por ítem; los precios y recetas son los
    actuales del catálogo.
    En estados cerrados: lee los snapshots almacenados en BudgetItem.
    """

    @classmethod
    def compute(cls, budget: "Budget") -> BudgetTotals:
        from apps.task_master.services import TaskCostCalculator

        if budget.is_locked:
            return cls._from_snapshot(budget)

        # Live calc.
        materials = Decimal("0")
        labor = Decimal("0")
        subcontracts = Decimal("0")
        for item in budget.items.select_related("task__output_unit"):
            breakdown = TaskCostCalculator.calculate(
                item.task,
                currency=budget.currency,
                date=budget.pricing_date or localdate(),
                rate_type=budget.exchange_rate_type,
            )
            qty = Decimal(item.quantity or 0)
            materials += breakdown.total_materials * qty
            labor += breakdown.total_labor * qty
            # En el breakdown actual no separamos subcontracts del bucket
            # "materials" — son materials por defecto. Cuando agreguemos
            # tracking detallado se separa.
        subtotal = materials + labor + subcontracts
        margin_amount = (subtotal * (budget.margin_pct or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"))
        total_with_margin = (subtotal + margin_amount).quantize(Decimal("0.01"))
        return BudgetTotals(
            materials=materials.quantize(Decimal("0.01")),
            labor=labor.quantize(Decimal("0.01")),
            subcontracts=subcontracts.quantize(Decimal("0.01")),
            subtotal=subtotal.quantize(Decimal("0.01")),
            margin_amount=margin_amount,
            total_with_margin=total_with_margin,
        )

    @classmethod
    def _from_snapshot(cls, budget: "Budget") -> BudgetTotals:
        materials = budget.materials_cost or Decimal("0")
        labor = budget.labor_cost or Decimal("0")
        subcontracts = budget.subcontracts_cost or Decimal("0")
        subtotal = materials + labor + subcontracts
        margin_amount = (subtotal * (budget.margin_pct or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"))
        return BudgetTotals(
            materials=materials, labor=labor, subcontracts=subcontracts,
            subtotal=subtotal, margin_amount=margin_amount,
            total_with_margin=budget.total_with_margin or (subtotal + margin_amount),
        )


class BudgetSnapshotService:
    """Congela todos los campos del Budget en una fecha dada."""

    @classmethod
    def freeze(cls, budget: "Budget", pricing_date: _date | None = None) -> "Budget":
        from apps.pricing.services import CurrencyConversionService
        from apps.task_master.services import TaskCostCalculator

        if pricing_date is None:
            pricing_date = localdate()

        budget.pricing_date = pricing_date

        # Si hay un rate_type elegido, congelar su valor a la fecha.
        if budget.exchange_rate_type_id:
            try:
                rate = CurrencyConversionService.get_rate(
                    budget.exchange_rate_type, date=pricing_date,
                )
                budget.exchange_rate_value = rate.rate
            except Exception:
                budget.exchange_rate_value = None

        materials = Decimal("0")
        labor = Decimal("0")
        subcontracts = Decimal("0")

        for item in budget.items.select_related("task__output_unit"):
            breakdown = TaskCostCalculator.calculate(
                item.task,
                currency=budget.currency,
                date=pricing_date,
                rate_type=budget.exchange_rate_type,
            )
            qty = Decimal(item.quantity or 0)
            item.task_version = item.task.version
            item.unit_cost = breakdown.total.quantize(Decimal("0.0001"))
            item.materials_cost = (breakdown.total_materials * qty).quantize(Decimal("0.01"))
            item.labor_cost = (breakdown.total_labor * qty).quantize(Decimal("0.01"))
            item.subcontracts_cost = Decimal("0")  # se separa cuando exista el bucket
            item.total_cost = (item.unit_cost * qty).quantize(Decimal("0.01"))
            item.recipe_snapshot = cls._serialize_recipe(breakdown)
            item.save(update_fields=[
                "task_version", "unit_cost", "materials_cost", "labor_cost",
                "subcontracts_cost", "total_cost", "recipe_snapshot", "updated_at",
            ])

            materials += item.materials_cost
            labor += item.labor_cost
            subcontracts += item.subcontracts_cost

        budget.materials_cost = materials
        budget.labor_cost = labor
        budget.subcontracts_cost = subcontracts
        subtotal = materials + labor + subcontracts
        margin = (subtotal * (budget.margin_pct or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"))
        budget.total_with_margin = (subtotal + margin).quantize(Decimal("0.01"))
        # total_in_ars / total_in_usd: por simplicidad guardamos el subtotal en la
        # moneda del budget; conversión multi-moneda en pulido.
        if budget.currency.code == "ARS":
            budget.total_in_ars = budget.total_with_margin
        elif budget.currency.code == "USD":
            budget.total_in_usd = budget.total_with_margin
        budget.save()
        return budget

    @staticmethod
    def _serialize_recipe(breakdown) -> dict:
        """Convierte un CostBreakdown a JSON-serializable."""
        return {
            "item_label": breakdown.item_label,
            "output_unit_symbol": breakdown.output_unit_symbol,
            "currency_code": breakdown.currency_code,
            "total": str(breakdown.total),
            "total_materials": str(breakdown.total_materials),
            "total_labor": str(breakdown.total_labor),
            "components": [
                {
                    "source_type": c.source_type,
                    "label": c.label,
                    "quantity_per_unit": str(c.quantity_per_unit),
                    "unit_cost": str(c.unit_cost),
                    "total": str(c.total),
                    "classification": c.classification,
                }
                for c in breakdown.components
            ],
        }


class BudgetApprovalService:
    """Maneja aprobación y supersedencia entre versiones."""

    @classmethod
    def submit(cls, budget: "Budget") -> "Budget":
        from .models import Budget

        if budget.status != Budget.Status.DRAFT:
            raise ValueError("Solo se pueden presentar borradores.")
        BudgetSnapshotService.freeze(budget)
        budget.status = Budget.Status.SUBMITTED
        budget.save(update_fields=["status", "updated_at"])
        return budget

    @classmethod
    def approve(cls, budget: "Budget", user) -> "Budget":
        from .models import Budget

        if budget.status not in {Budget.Status.SUBMITTED, Budget.Status.DRAFT}:
            raise ValueError("Solo se aprueban borradores o presentados.")
        if budget.status == Budget.Status.DRAFT:
            BudgetSnapshotService.freeze(budget)

        # Reemplazar otras aprobadas del mismo proyecto.
        Budget.objects.filter(
            project=budget.project, status=Budget.Status.APPROVED,
        ).exclude(pk=budget.pk).update(status=Budget.Status.SUPERSEDED)

        budget.status = Budget.Status.APPROVED
        budget.approved_by = user
        budget.approved_at = tz_now()
        budget.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return budget

    @classmethod
    def reject(cls, budget: "Budget") -> "Budget":
        from .models import Budget

        if budget.status not in {Budget.Status.SUBMITTED, Budget.Status.DRAFT}:
            raise ValueError("Solo se rechazan borradores o presentados.")
        budget.status = Budget.Status.REJECTED
        budget.save(update_fields=["status", "updated_at"])
        return budget

    @classmethod
    def clone_as_new_version(cls, budget: "Budget", user) -> "Budget":
        """Crea P{n+1} en draft copiando los items del actual."""
        from .models import Budget, BudgetItem

        next_version = (
            Budget.objects.filter(project=budget.project)
            .order_by("-version").first().version + 1
        )
        new_budget = Budget.objects.create(
            project=budget.project,
            name=f"{budget.name or 'Presupuesto'} P{next_version}",
            version=next_version,
            status=Budget.Status.DRAFT,
            currency=budget.currency,
            margin_pct=budget.margin_pct,
            exchange_rate_type=budget.exchange_rate_type,
            created_by=user,
        )
        for item in budget.items.all():
            BudgetItem.objects.create(
                budget=new_budget,
                task=item.task,
                quantity=item.quantity,
                order=item.order,
                notes=item.notes,
            )
        return new_budget
