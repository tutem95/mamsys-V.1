"""TaskCostCalculator: resuelve recursivamente el costo de una Task o Mix.

Para cada componente:
- material → PriceLookupService.get_current_price(material, currency, date)
- subcontract → PriceLookupService.get_current_price(subcontract, currency, date)
- labor (position) → último Valor Jornal de esa Position (del último
  PayrollEntry de un empleado en ese puesto, o fallback al PositionPlus
  reciente — pragmático).
- sub_mix → calculate_cost(sub_mix, ...) recursivo
- sub_task → calculate_cost(sub_task, ...) recursivo

Devuelve un CostBreakdown navegable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.utils.timezone import localdate

if TYPE_CHECKING:
    from apps.currencies.models import Currency

    from .models import Mix, Task, TaskComponent


@dataclass
class CostLine:
    component_id: int | None
    source_type: str  # material / labor / subcontract / sub_mix / sub_task
    label: str
    quantity_per_unit: Decimal
    unit_cost: Decimal
    total: Decimal
    classification: str  # materials / labor


@dataclass
class CostBreakdown:
    item_label: str
    output_unit_symbol: str
    total: Decimal
    total_materials: Decimal = Decimal("0")
    total_labor: Decimal = Decimal("0")
    currency_code: str = "ARS"
    components: list[CostLine] = field(default_factory=list)
    # Sub-breakdowns para sub_mix/sub_task (navegables en UI).
    sub_breakdowns: dict[int, "CostBreakdown"] = field(default_factory=dict)


class TaskCostCalculator:
    """Calcula el costo de una Task o Mix a una fecha y moneda dadas."""

    @classmethod
    def calculate(
        cls,
        task_or_mix,
        currency: "Currency | None" = None,
        date: _date | None = None,
        rate_type=None,
    ) -> CostBreakdown:
        from apps.currencies.models import Currency

        if date is None:
            date = localdate()
        if currency is None:
            currency = Currency.objects.get(code="ARS")

        visited: set[tuple[str, int]] = set()
        return cls._calculate(task_or_mix, currency, date, rate_type, visited)

    @classmethod
    def _calculate(
        cls, item, currency, date, rate_type, visited: set[tuple[str, int]],
    ) -> CostBreakdown:
        from .models import Mix, Task

        kind = "mix" if isinstance(item, Mix) else "task"
        key = (kind, item.pk)
        if key in visited:
            # Salvaguarda en runtime aunque haya un ciclo (no debería pasar por validators).
            return CostBreakdown(
                item_label=item.name, output_unit_symbol=str(item.output_unit),
                total=Decimal("0"), currency_code=currency.code,
            )
        visited.add(key)

        breakdown = CostBreakdown(
            item_label=item.name,
            output_unit_symbol=str(item.output_unit),
            total=Decimal("0"),
            currency_code=currency.code,
        )

        if kind == "mix":
            components_qs = item.components.select_related("material", "sub_mix", "input_unit")
        else:
            components_qs = item.components.select_related(
                "material", "position", "subcontract", "sub_mix", "sub_task", "input_unit",
            )

        for comp in components_qs:
            line = cls._resolve_component(comp, currency, date, rate_type, visited, breakdown)
            if line is not None:
                breakdown.components.append(line)
                breakdown.total += line.total
                if line.classification == "labor":
                    breakdown.total_labor += line.total
                else:
                    breakdown.total_materials += line.total

        breakdown.total = breakdown.total.quantize(Decimal("0.0001"))
        breakdown.total_materials = breakdown.total_materials.quantize(Decimal("0.0001"))
        breakdown.total_labor = breakdown.total_labor.quantize(Decimal("0.0001"))
        visited.discard(key)
        return breakdown

    # ----------------------------------------------------------------------
    # Resolución de un componente individual
    # ----------------------------------------------------------------------

    @classmethod
    def _resolve_component(
        cls, comp, currency, date, rate_type, visited, parent_breakdown,
    ) -> CostLine | None:
        from .models import MixComponent, TaskComponent

        qty = Decimal(comp.quantity_per_unit or 0)

        # MixComponent: material o sub_mix.
        if isinstance(comp, MixComponent):
            if comp.material_id:
                unit_cost = cls._material_price(comp.material, currency, date, rate_type)
                total = (qty * unit_cost).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="material",
                    label=comp.material.name,
                    quantity_per_unit=qty, unit_cost=unit_cost, total=total,
                    classification="materials",
                )
            if comp.sub_mix_id:
                sub = cls._calculate(comp.sub_mix, currency, date, rate_type, visited)
                parent_breakdown.sub_breakdowns[comp.sub_mix_id] = sub
                total = (qty * sub.total).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="sub_mix",
                    label=f"{comp.sub_mix.name} (mix)",
                    quantity_per_unit=qty, unit_cost=sub.total, total=total,
                    classification="materials",
                )
            return None

        # TaskComponent.
        if isinstance(comp, TaskComponent):
            st = comp.source_type
            if st == "material" and comp.material_id:
                unit_cost = cls._material_price(comp.material, currency, date, rate_type)
                total = (qty * unit_cost).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="material",
                    label=comp.material.name,
                    quantity_per_unit=qty, unit_cost=unit_cost, total=total,
                    classification=comp.classification or "materials",
                )
            if st == "subcontract" and comp.subcontract_id:
                unit_cost = cls._subcontract_price(comp.subcontract, currency, date, rate_type)
                total = (qty * unit_cost).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="subcontract",
                    label=comp.subcontract.name,
                    quantity_per_unit=qty, unit_cost=unit_cost, total=total,
                    classification=comp.classification or "materials",
                )
            if st == "labor" and comp.position_id:
                unit_cost = cls._labor_cost(comp.position, currency, date, rate_type)
                total = (qty * unit_cost).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="labor",
                    label=f"{comp.position.name} (jornal)",
                    quantity_per_unit=qty, unit_cost=unit_cost, total=total,
                    classification="labor",
                )
            if st == "sub_mix" and comp.sub_mix_id:
                sub = cls._calculate(comp.sub_mix, currency, date, rate_type, visited)
                parent_breakdown.sub_breakdowns[comp.sub_mix_id] = sub
                total = (qty * sub.total).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="sub_mix",
                    label=f"{comp.sub_mix.name} (mix)",
                    quantity_per_unit=qty, unit_cost=sub.total, total=total,
                    classification=comp.classification or "materials",
                )
            if st == "sub_task" and comp.sub_task_id:
                sub = cls._calculate(comp.sub_task, currency, date, rate_type, visited)
                parent_breakdown.sub_breakdowns[comp.sub_task_id] = sub
                total = (qty * sub.total).quantize(Decimal("0.0001"))
                return CostLine(
                    component_id=comp.pk, source_type="sub_task",
                    label=f"{comp.sub_task.name} (tarea)",
                    quantity_per_unit=qty, unit_cost=sub.total, total=total,
                    classification=comp.classification or "materials",
                )
        return None

    # ----------------------------------------------------------------------
    # Lookups específicos
    # ----------------------------------------------------------------------

    @staticmethod
    def _material_price(material, currency, date, rate_type) -> Decimal:
        from apps.pricing.services import PriceLookupService, PriceNotFoundError
        try:
            result = PriceLookupService.get_current_price(
                material, currency=currency, date=date, rate_type=rate_type,
            )
            return result.amount
        except PriceNotFoundError:
            # Fallback al last_known_price del Material.
            return Decimal(material.last_known_price or 0)

    @staticmethod
    def _subcontract_price(subcontract, currency, date, rate_type) -> Decimal:
        from apps.pricing.services import PriceLookupService, PriceNotFoundError
        try:
            result = PriceLookupService.get_current_price(
                subcontract, currency=currency, date=date, rate_type=rate_type,
            )
            return result.amount
        except PriceNotFoundError:
            return Decimal(subcontract.last_known_price or 0)

    @staticmethod
    def _labor_cost(position, currency, date, rate_type) -> Decimal:
        """Último Valor Jornal para una Position.

        Heurística: tomar el `value_jornal` más reciente en `PayrollEntry`
        de un empleado con esa posición. Si no hay, devolver 0 (la UI lo
        marca como "Sin dato de jornal").
        """
        from apps.payroll.models import PayrollEntry

        entry = (
            PayrollEntry.objects
            .filter(employee__position_id=position.pk, value_jornal__gt=0)
            .order_by("-payroll_period__year", "-payroll_period__month", "-payroll_period__period_number")
            .first()
        )
        if entry is None:
            return Decimal("0")
        # TODO: conversión si entry.currency != currency. Por ahora asume ARS.
        return Decimal(entry.value_jornal)
