"""Catálogos base de Fase 2.

Esta primera entrega cubre los catálogos más fundamentales (sin dependencias
externas) que habilitan a las fases siguientes:

- Rubro: clasificación gruesa de trabajos (estructura, albañilería, etc.).
- Subrubro: subdivisión de un Rubro (FK estricta).
- Unit: unidad de medida (m², m³, JORNAL, UNI, ML, etc.).
- BusinessComponent: clasificador transversal (TERRENO, VENTA UF, etc.).

Catálogos pendientes que se suman en próximas entregas: Currency (SHARED),
Material, Supplier, Subcontract, Bank, BankAccount, Position, Team,
Warehouse, EmployeeStatus, ProjectStatus, ExtraordinaryConcept,
TrackingCategory, ExchangeRateType.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import CatalogItem


class Rubro(CatalogItem):
    """Clasificación gruesa de trabajos: TRABAJOS PRELIMINARES, ESTRUCTURA, etc."""

    class Meta(CatalogItem.Meta):
        verbose_name = "Rubro"
        verbose_name_plural = "Rubros"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="rubro_unique_name"),
        ]


class Subrubro(CatalogItem):
    """Subdivisión de un Rubro. Pertenece a un único Rubro (jerarquía estricta)."""

    rubro = models.ForeignKey(Rubro, on_delete=models.PROTECT, related_name="subrubros")

    class Meta(CatalogItem.Meta):
        verbose_name = "Subrubro"
        verbose_name_plural = "Subrubros"
        constraints = [
            models.UniqueConstraint(fields=["rubro", "name"], name="subrubro_unique_per_rubro"),
        ]

    def __str__(self) -> str:
        return f"{self.rubro.name} / {self.name}"


class Unit(CatalogItem):
    """Unidad de medida. El `name` es descriptivo, `symbol` lo que se muestra."""

    class Category(models.TextChoices):
        LENGTH = "length", "Longitud"
        AREA = "area", "Área"
        VOLUME = "volume", "Volumen"
        WEIGHT = "weight", "Peso"
        TIME = "time", "Tiempo"
        GLOBAL = "global", "Global"
        OTHER = "other", "Otro"

    symbol = models.CharField(max_length=20)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)

    class Meta(CatalogItem.Meta):
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"
        constraints = [
            models.UniqueConstraint(fields=["symbol"], name="unit_unique_symbol"),
        ]

    def __str__(self) -> str:
        return self.symbol


class BusinessComponent(CatalogItem):
    """Componente transversal de negocio (TERRENO, VENTA UF, etc.).

    No está atado a Rubro/Subrubro: cualquier operación puede combinar cualquier
    Componente con cualquier Subrubro.
    """

    class Meta(CatalogItem.Meta):
        verbose_name = "Componente"
        verbose_name_plural = "Componentes"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="businesscomponent_unique_name"),
        ]


# ---------------------------------------------------------------------------
# Catálogos simples (sin relaciones a otros catálogos)
# ---------------------------------------------------------------------------


class ProjectStatus(CatalogItem):
    """Estados de obra: Solo Terreno, En Construcción, Completada, etc."""

    class Meta(CatalogItem.Meta):
        verbose_name = "Estado de obra"
        verbose_name_plural = "Estados de obra"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="projectstatus_unique_name"),
        ]


class EmployeeStatus(CatalogItem):
    """Estados de empleado: Activo, Suspendido, Renuncio, Despedido."""

    class Meta(CatalogItem.Meta):
        verbose_name = "Estado de empleado"
        verbose_name_plural = "Estados de empleado"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="employeestatus_unique_name"),
        ]


class Position(CatalogItem):
    """Puesto de trabajo: Ayudante, Medio Oficial, Oficial, RT, etc."""

    class Meta(CatalogItem.Meta):
        verbose_name = "Puesto"
        verbose_name_plural = "Puestos"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="position_unique_name"),
        ]


class Bank(CatalogItem):
    """Catálogo de bancos (Galicia, Ciudad, Provincia, etc.).

    Las cuentas bancarias específicas (BankAccount) viven aparte y necesitan
    Currency + Company; se sumarán cuando esos catálogos existan.
    """

    class Meta(CatalogItem.Meta):
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="bank_unique_name"),
        ]


class ExtraordinaryConcept(CatalogItem):
    """Concepto extraordinario de quincena: Adelanto, Bono, Aguinaldo, etc."""

    class Type(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Egreso"

    type = models.CharField(max_length=20, choices=Type.choices)

    class Meta(CatalogItem.Meta):
        verbose_name = "Concepto extraordinario"
        verbose_name_plural = "Conceptos extraordinarios"
        constraints = [
            models.UniqueConstraint(fields=["type", "name"], name="extraordinary_unique_name_per_type"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


class TrackingCategory(CatalogItem):
    """Sub-planilla configurable de seguimiento por obra. Cada empresa define las suyas."""

    color = models.CharField(max_length=7, default="#9fc5e8", help_text="Hex color, ej: #3d85c6.")

    class Meta(CatalogItem.Meta):
        verbose_name = "Categoría de seguimiento"
        verbose_name_plural = "Categorías de seguimiento"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="trackingcategory_unique_name"),
        ]


# ---------------------------------------------------------------------------
# Catálogos con relaciones a otros catálogos
# ---------------------------------------------------------------------------


class Supplier(CatalogItem):
    """Proveedor.

    Vende en uno o más rubros (M2M). `category` es libre (ARIDOS, CORRALON, etc.).
    """

    category = models.CharField(max_length=50, blank=True)
    rubros = models.ManyToManyField(Rubro, related_name="suppliers", blank=True)

    contact_name = models.CharField(max_length=120, blank=True, help_text="Asistente / referente del proveedor.")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField("CUIT", max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta(CatalogItem.Meta):
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="supplier_unique_name"),
            models.UniqueConstraint(fields=["code"], condition=~models.Q(code=""), name="supplier_unique_code"),
        ]


class Material(CatalogItem):
    """Material comprable. Se usa como ítem en Compras y en recetas de Tareas."""

    rubro = models.ForeignKey(Rubro, on_delete=models.PROTECT, related_name="materials")
    subrubro = models.ForeignKey(
        Subrubro,
        on_delete=models.PROTECT,
        related_name="materials",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="materials")
    description = models.TextField(blank=True)

    # Cache poblado automáticamente desde compras (ver Fase 4).
    # TODO(currency): cuando exista el modelo Currency (SHARED), agregar
    # last_known_currency como FK. Por ahora guardamos solo el monto.
    last_known_price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Último precio conocido (cache, lo actualizan las compras).",
    )

    class Meta(CatalogItem.Meta):
        verbose_name = "Material"
        verbose_name_plural = "Materiales"
        constraints = [
            models.UniqueConstraint(fields=["name", "unit"], name="material_unique_name_per_unit"),
        ]


class Subcontract(CatalogItem):
    """Catálogo de tipos de subcontrato (Estudio de Suelo, Cálculo Estructural, etc.).

    Se usa como ítem cuando una Compra tiene is_subcontract=True.
    """

    description = models.TextField(blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="subcontracts")
    typical_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="typical_subcontracts",
    )

    # Mismo TODO(currency) que en Material.
    last_known_price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
    )

    class Meta(CatalogItem.Meta):
        verbose_name = "Subcontrato"
        verbose_name_plural = "Subcontratos"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="subcontract_unique_name"),
        ]
