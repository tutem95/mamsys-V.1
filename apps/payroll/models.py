"""Nómina — Turno A: Employee y datos asociados.

Modelo separa intencionalmente:
- `Employee` (datos laborales): poco sensibles, todos los roles con permiso de
  empleados pueden ver.
- `EmployeePersonalData` (OneToOne): documento, CUIL, fecha de nacimiento, etc.
  Sensible. En Turno futuro se gatea con permiso VIEW_SENSITIVE_EMPLOYEE_DATA.
- `EmployeeBanking` (OneToOne): CBU, CVU. Más sensible aún.
- `EmergencyContact` (1:N): no sensible.

Quincenas, plus, allocations y CS llegan en Turnos B/C/D.
"""

from __future__ import annotations

from datetime import date as _date

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


class Employee(TimestampedModel):
    """Datos laborales del empleado. Es la entidad "raíz" de la nómina."""

    class DocumentType(models.TextChoices):
        DNI = "DNI", "DNI"
        PAS = "PAS", "Pasaporte"
        OTHER = "OTHER", "Otro"

    internal_id = models.CharField(
        max_length=30, blank=True,
        help_text="ID interno (numeración propia de la org).",
    )

    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT,
        related_name="employees",
        help_text="Sociedad que paga el sueldo.",
    )
    status = models.ForeignKey(
        "catalog.EmployeeStatus", on_delete=models.PROTECT,
        related_name="employees",
        null=True, blank=True,
    )
    position = models.ForeignKey(
        "catalog.Position", on_delete=models.PROTECT,
        related_name="employees",
        null=True, blank=True,
    )
    teams = models.ManyToManyField(
        "catalog.Team",
        related_name="members",
        blank=True,
        help_text="Equipos a los que pertenece. Puede estar en varios.",
    )
    boss = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reports",
        help_text="Jefe directo / Jefe de Obra.",
    )
    primary_rubro = models.ForeignKey(
        "catalog.Rubro", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="primary_employees",
        help_text="Solo informativo — sugerencia de imputación principal.",
    )

    hire_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    arca_registered = models.BooleanField(
        "Alta en ARCA/AFIP", default=False,
    )

    # Cache que poblará la Quincena (Turno B) con el último value_jornal cobrado.
    last_known_salary = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True,
    )
    last_known_currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ("-hire_date", "id")
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["position"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "internal_id"],
                condition=~models.Q(internal_id=""),
                name="employee_unique_internal_id_per_company",
            ),
        ]

    def __str__(self) -> str:
        try:
            personal = self.personal_data
        except EmployeePersonalData.DoesNotExist:
            personal = None
        if personal:
            return personal.full_name
        if self.internal_id:
            return f"Empleado #{self.internal_id}"
        return f"Empleado #{self.pk}"

    @property
    def full_name(self) -> str:
        try:
            return self.personal_data.full_name
        except EmployeePersonalData.DoesNotExist:
            return str(self)


class EmployeePersonalData(TimestampedModel):
    """Datos personales del empleado (sensibles).

    Se modela 1-a-1 separado para poder gatear el acceso con un permiso
    específico (`VIEW_SENSITIVE_EMPLOYEE_DATA`) en próximos turnos.
    """

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Soltero/a"
        MARRIED = "married", "Casado/a"
        DIVORCED = "divorced", "Divorciado/a"
        WIDOWED = "widowed", "Viudo/a"
        OTHER = "other", "Otro"

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE,
        related_name="personal_data",
    )

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)

    nationality = models.CharField(max_length=80, blank=True)
    document_type = models.CharField(
        max_length=10, choices=Employee.DocumentType.choices,
        default=Employee.DocumentType.DNI,
    )
    document_number = models.CharField(max_length=30, blank=True)
    cuil = models.CharField("CUIL", max_length=20, blank=True)

    birth_date = models.DateField(null=True, blank=True)
    marital_status = models.CharField(
        max_length=20, choices=MaritalStatus.choices, blank=True,
    )
    children_count = models.PositiveIntegerField(default=0)

    phone_landline = models.CharField("Teléfono fijo", max_length=40, blank=True)
    phone_mobile = models.CharField("Celular", max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Datos personales"
        verbose_name_plural = "Datos personales"

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or "(sin nombre)"

    @property
    def age(self) -> int | None:
        if self.birth_date is None:
            return None
        today = _date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years


class EmployeeBanking(TimestampedModel):
    """Datos bancarios del empleado. Lo más sensible.

    En el futuro, gateado por `VIEW_SENSITIVE_EMPLOYEE_DATA` para CBU/CVU.
    """

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE,
        related_name="banking",
    )

    bank = models.ForeignKey(
        "catalog.Bank", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="employee_banking",
    )
    cbu = models.CharField("CBU", max_length=22, blank=True)
    cvu_mercado_libre = models.CharField(
        "CVU billetera virtual", max_length=22, blank=True,
        help_text="Mercado Pago / billeteras virtuales.",
    )

    class Meta:
        verbose_name = "Datos bancarios"
        verbose_name_plural = "Datos bancarios"

    def __str__(self) -> str:
        return f"Banking de {self.employee_id}"


class EmergencyContact(TimestampedModel):
    """Contacto de emergencia. Un empleado puede tener varios."""

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name="emergency_contacts",
    )
    full_name = models.CharField(max_length=160)
    relationship = models.CharField(
        max_length=80, blank=True,
        help_text="Esposo/a, padre, madre, hermano/a, etc.",
    )
    phone = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "Contacto de emergencia"
        verbose_name_plural = "Contactos de emergencia"
        ordering = ("id",)

    def __str__(self) -> str:
        return self.full_name
