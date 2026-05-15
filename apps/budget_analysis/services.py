"""Servicio de cruce Presupuesto vs Real.

Toma un Budget (idealmente snapshot) y junta:
- Compras del Project hasta cutoff_date (PurchaseItem y cabecera s/items).
- Nómina del Project: PayrollAllocation hasta cutoff_date.
- Opcional: CS prorrateado (ya viene en allocation.social_charges_amount).

Devuelve `CrossResult` con:
- Totales planned/actual/variance.
- Breakdown por rubro y por tarea cuando hay link.
- Listas de purchases / payroll_allocations que aportaron.

Convierte todo a la moneda elegida usando CurrencyConversionService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import Q, Sum
from django.utils.timezone import localdate

if TYPE_CHECKING:
    from apps.budgets.models import Budget
    from apps.currencies.models import Currency
    from apps.pricing.models import ExchangeRateType


@dataclass
class CategoryTotals:
    label: str
    planned: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")

    @property
    def variance(self) -> Decimal:
        return (self.actual - self.planned).quantize(Decimal("0.01"))

    @property
    def variance_pct(self) -> Decimal:
        if self.planned == 0:
            return Decimal("0") if self.actual == 0 else Decimal("100")
        return ((self.actual - self.planned) / self.planned * Decimal("100")).quantize(Decimal("0.01"))


@dataclass
class RubroBreakdown:
    rubro_id: int | None
    rubro_name: str
    planned: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")

    @property
    def variance(self) -> Decimal:
        return (self.actual - self.planned).quantize(Decimal("0.01"))

    @property
    def variance_pct(self) -> Decimal:
        if self.planned == 0:
            return Decimal("0") if self.actual == 0 else Decimal("100")
        return ((self.actual - self.planned) / self.planned * Decimal("100")).quantize(Decimal("0.01"))


@dataclass
class TaskBreakdown:
    task_id: int
    task_name: str
    quantity: Decimal
    planned: Decimal
    actual: Decimal

    @property
    def variance(self) -> Decimal:
        return (self.actual - self.planned).quantize(Decimal("0.01"))

    @property
    def variance_pct(self) -> Decimal:
        if self.planned == 0:
            return Decimal("0") if self.actual == 0 else Decimal("100")
        return ((self.actual - self.planned) / self.planned * Decimal("100")).quantize(Decimal("0.01"))


@dataclass
class CrossResult:
    project_name: str
    budget_label: str
    cutoff_date: _date
    currency_code: str

    materials: CategoryTotals = field(default_factory=lambda: CategoryTotals(label="Materiales"))
    labor: CategoryTotals = field(default_factory=lambda: CategoryTotals(label="Mano de obra"))
    subcontracts: CategoryTotals = field(default_factory=lambda: CategoryTotals(label="Subcontratos"))

    rubros: list[RubroBreakdown] = field(default_factory=list)
    tasks: list[TaskBreakdown] = field(default_factory=list)

    purchases_count: int = 0
    allocations_count: int = 0
    actual_unlinked: Decimal = Decimal("0")  # plata real sin tarea asignada

    @property
    def total_planned(self) -> Decimal:
        return (self.materials.planned + self.labor.planned + self.subcontracts.planned).quantize(Decimal("0.01"))

    @property
    def total_actual(self) -> Decimal:
        return (self.materials.actual + self.labor.actual + self.subcontracts.actual).quantize(Decimal("0.01"))

    @property
    def variance_amount(self) -> Decimal:
        return (self.total_actual - self.total_planned).quantize(Decimal("0.01"))

    @property
    def variance_pct(self) -> Decimal:
        if self.total_planned == 0:
            return Decimal("0") if self.total_actual == 0 else Decimal("100")
        return ((self.total_actual - self.total_planned) / self.total_planned * Decimal("100")).quantize(Decimal("0.01"))


class BudgetActualCrossService:
    """Arma el cruce Budget ↔ Compras/Nómina."""

    @classmethod
    def compute(
        cls,
        budget: "Budget",
        cutoff_date: _date | None = None,
        currency: "Currency | None" = None,
        rate_type: "ExchangeRateType | None" = None,
    ) -> CrossResult:
        from apps.currencies.models import Currency
        from apps.payroll.models import PayrollAllocation
        from apps.pricing.services import CurrencyConversionService
        from apps.procurement.models import Purchase, PurchaseItem
        from apps.task_master.models import Task

        if cutoff_date is None:
            cutoff_date = localdate()
        if currency is None:
            currency = budget.currency or Currency.objects.get(code="ARS")

        result = CrossResult(
            project_name=budget.project.name,
            budget_label=f"P{budget.version}",
            cutoff_date=cutoff_date,
            currency_code=currency.code,
        )

        # ----- Planned (del snapshot del Budget) -----
        result.materials.planned = budget.materials_cost or Decimal("0")
        result.labor.planned = budget.labor_cost or Decimal("0")
        result.subcontracts.planned = budget.subcontracts_cost or Decimal("0")

        # Por tarea (planned) — vienen del BudgetItem snapshot.
        task_planned: dict[int, Decimal] = {}
        task_meta: dict[int, dict] = {}
        for item in budget.items.select_related("task__rubro"):
            task_planned[item.task_id] = item.total_cost or Decimal("0")
            task_meta[item.task_id] = {
                "name": item.task.name,
                "quantity": item.quantity,
                "rubro_id": item.task.rubro_id,
                "rubro_name": item.task.rubro.name,
            }

        # ----- Actual: Compras -----
        purchases = (
            Purchase.objects
            .filter(
                project=budget.project,
                invoice_date__lte=cutoff_date,
            )
            .exclude(status=Purchase.Status.CANCELLED)
            .select_related("rubro", "original_currency")
            .prefetch_related("items")
        )
        result.purchases_count = purchases.count()

        rubro_actual: dict[int, Decimal] = {}
        rubro_labels: dict[int, str] = {}
        task_actual: dict[int, Decimal] = {}

        materials_actual = Decimal("0")
        subcontracts_actual = Decimal("0")
        unlinked = Decimal("0")

        for purchase in purchases:
            converted_total = cls._convert(
                purchase.total_amount, purchase.original_currency, currency,
                purchase.invoice_date, rate_type,
            )
            items = list(purchase.items.all())
            if items:
                items_subtotal = sum(((it.total or Decimal("0")) for it in items), Decimal("0"))
                # Si los items no cuadran con el bruto, prorrateamos.
                ratio = (
                    (converted_total / items_subtotal)
                    if items_subtotal > 0
                    else Decimal("0")
                )
                for it in items:
                    converted = (it.total * ratio) if items_subtotal > 0 else Decimal("0")
                    if purchase.is_subcontract:
                        subcontracts_actual += converted
                    else:
                        materials_actual += converted
                    # Por rubro: usar el rubro del subrubro del item si está,
                    # sino el rubro de la cabecera.
                    rubro_id = purchase.rubro_id
                    if it.subrubro_id:
                        rubro_id = it.subrubro.rubro_id if hasattr(it, "subrubro") and it.subrubro else rubro_id
                    rubro_actual[rubro_id] = rubro_actual.get(rubro_id, Decimal("0")) + converted
                    rubro_labels[rubro_id] = purchase.rubro.name
                    # Por task si está vinculado.
                    if it.task_id:
                        task_actual[it.task_id] = task_actual.get(it.task_id, Decimal("0")) + converted
                    else:
                        # Sin task → no contribuye a granularidad fina.
                        pass
            else:
                # Sin items: la cabecera entera al rubro.
                if purchase.is_subcontract:
                    subcontracts_actual += converted_total
                else:
                    materials_actual += converted_total
                rubro_id = purchase.rubro_id
                rubro_actual[rubro_id] = rubro_actual.get(rubro_id, Decimal("0")) + converted_total
                rubro_labels[rubro_id] = purchase.rubro.name

        result.materials.actual = materials_actual.quantize(Decimal("0.01"))
        result.subcontracts.actual = subcontracts_actual.quantize(Decimal("0.01"))

        # ----- Actual: Nómina (allocations imputadas a este project) -----
        allocations = (
            PayrollAllocation.objects
            .filter(
                project=budget.project,
                payroll_entry__payroll_period__end_date__lte=cutoff_date,
            )
            .select_related("payroll_entry__payroll_period", "payroll_entry__currency")
        )
        result.allocations_count = allocations.count()

        labor_actual = Decimal("0")
        for alloc in allocations:
            # Asumimos misma moneda que el budget — refinamiento multi-moneda
            # vía CurrencyConversionService en próxima pasada.
            total_alloc = (alloc.net_amount or Decimal("0")) + (alloc.social_charges_amount or Decimal("0"))
            if alloc.payroll_entry.currency_id != currency.pk:
                total_alloc = cls._convert(
                    total_alloc,
                    alloc.payroll_entry.currency,
                    currency,
                    alloc.payroll_entry.payroll_period.end_date,
                    rate_type,
                )
            labor_actual += total_alloc
            if alloc.task_id:
                task_actual[alloc.task_id] = task_actual.get(alloc.task_id, Decimal("0")) + total_alloc

        result.labor.actual = labor_actual.quantize(Decimal("0.01"))

        # ----- Armar rubros (incluyendo los del budget aunque no tengan actual) -----
        all_rubros: dict[int, RubroBreakdown] = {}
        # Planificado por rubro = suma de items del budget por rubro.
        for tid, meta in task_meta.items():
            rid = meta["rubro_id"]
            if rid not in all_rubros:
                all_rubros[rid] = RubroBreakdown(rubro_id=rid, rubro_name=meta["rubro_name"])
            all_rubros[rid].planned += task_planned.get(tid, Decimal("0"))
        for rid, amt in rubro_actual.items():
            if rid not in all_rubros:
                all_rubros[rid] = RubroBreakdown(rubro_id=rid, rubro_name=rubro_labels.get(rid, "(sin nombre)"))
            all_rubros[rid].actual += amt
        result.rubros = sorted(
            all_rubros.values(),
            key=lambda r: r.actual + r.planned,
            reverse=True,
        )

        # ----- Armar tasks -----
        task_ids = set(task_planned.keys()) | set(task_actual.keys())
        tasks_qs = {t.pk: t for t in Task.objects.filter(pk__in=task_ids)}
        for tid in task_ids:
            t = tasks_qs.get(tid)
            if t is None:
                continue
            meta = task_meta.get(tid, {"quantity": Decimal("0")})
            result.tasks.append(TaskBreakdown(
                task_id=tid,
                task_name=t.name,
                quantity=meta.get("quantity", Decimal("0")),
                planned=task_planned.get(tid, Decimal("0")).quantize(Decimal("0.01")),
                actual=task_actual.get(tid, Decimal("0")).quantize(Decimal("0.01")),
            ))
        result.tasks.sort(key=lambda x: x.actual + x.planned, reverse=True)

        return result

    @staticmethod
    def _convert(amount, from_currency, to_currency, date, rate_type) -> Decimal:
        from apps.pricing.services import CurrencyConversionService, ExchangeRateNotFoundError

        if amount is None:
            return Decimal("0")
        amount = Decimal(amount)
        if from_currency.pk == to_currency.pk:
            return amount
        try:
            conv = CurrencyConversionService.convert(
                amount, from_currency, to_currency, date=date, rate_type=rate_type,
            )
            return conv.amount
        except ExchangeRateNotFoundError:
            # Fallback: usar amount sin convertir y avisar arriba (sin warning aquí).
            return amount


def serialize_result(result: CrossResult) -> dict:
    """JSON-serializable de CrossResult para persistir en BudgetVsActualReport.data."""
    return {
        "project_name": result.project_name,
        "budget_label": result.budget_label,
        "cutoff_date": result.cutoff_date.isoformat(),
        "currency_code": result.currency_code,
        "materials": {"planned": str(result.materials.planned), "actual": str(result.materials.actual)},
        "labor": {"planned": str(result.labor.planned), "actual": str(result.labor.actual)},
        "subcontracts": {"planned": str(result.subcontracts.planned), "actual": str(result.subcontracts.actual)},
        "rubros": [
            {
                "id": r.rubro_id, "name": r.rubro_name,
                "planned": str(r.planned), "actual": str(r.actual),
            }
            for r in result.rubros
        ],
        "tasks": [
            {
                "id": t.task_id, "name": t.task_name,
                "quantity": str(t.quantity),
                "planned": str(t.planned), "actual": str(t.actual),
            }
            for t in result.tasks
        ],
        "purchases_count": result.purchases_count,
        "allocations_count": result.allocations_count,
    }
