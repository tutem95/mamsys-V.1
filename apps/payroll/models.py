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


# ===========================================================================
# Quincena (Turno B)
# ===========================================================================

from decimal import Decimal, ROUND_HALF_UP

# Denominaciones de billetes ARS para el conteo automático.
BILL_DENOMINATIONS: tuple[int, ...] = (1000, 500, 200, 100, 50, 20, 10)


def round_to_multiple_of_10(amount: Decimal) -> Decimal:
    """Redondea al múltiplo de 10 más cercano (half-up)."""
    return (amount / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")


def calculate_bills(amount: int | Decimal) -> tuple[dict[int, int], int]:
    """Greedy: cuántos billetes de cada denominación + remanente.

    >>> calculate_bills(1340)
    ({1000: 1, 500: 0, 200: 1, 100: 1, 50: 0, 20: 2, 10: 0}, 0)
    """
    remaining = int(amount)
    bills: dict[int, int] = {}
    for d in BILL_DENOMINATIONS:
        bills[d] = remaining // d
        remaining -= bills[d] * d
    return bills, remaining


class PayrollPeriod(TimestampedModel):
    """Quincena de una sociedad.

    Una empresa tiene 2 quincenas por mes. Configura días, horas y plus
    generales (overtime y presentismo) a aplicar.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"
        PAID = "paid", "Pagada"

    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT,
        related_name="payroll_periods",
    )

    period_number = models.PositiveSmallIntegerField(
        help_text="1 o 2 (primera o segunda quincena del mes).",
    )
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()

    start_date = models.DateField()
    end_date = models.DateField()

    talonario_name = models.CharField(
        max_length=120, blank=True,
        help_text='Ej: "1era Quincena de Diciembre".',
    )

    # Días
    working_days = models.PositiveSmallIntegerField(default=10, help_text="Días laborales L-V.")
    saturdays = models.PositiveSmallIntegerField(default=2)
    holidays = models.PositiveSmallIntegerField(default=0)
    total_days = models.PositiveSmallIntegerField(default=12)

    # Horas
    hours_weekday = models.PositiveSmallIntegerField(default=8)
    hours_saturday = models.PositiveSmallIntegerField(default=7)
    total_hours = models.PositiveSmallIntegerField(default=94)

    # Plus generales (porcentajes con 2 decimales — ej: 12.00, 2.30).
    plus_overtime_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    plus_presentismo_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        verbose_name = "Quincena"
        verbose_name_plural = "Quincenas"
        ordering = ("-year", "-month", "-period_number")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month", "period_number"],
                name="payrollperiod_unique_per_company",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company.name} · {self.period_number}ª {self.month}/{self.year}"


class PositionPlus(TimestampedModel):
    """Plus por puesto y quincena (ej: $18 ayudante, $22 medio of., $25 of.).

    Es un adicional fijo por día trabajado, asociado al puesto del empleado.
    """

    payroll_period = models.ForeignKey(
        PayrollPeriod, on_delete=models.CASCADE,
        related_name="position_pluses",
    )
    position = models.ForeignKey(
        "catalog.Position", on_delete=models.PROTECT,
        related_name="period_pluses",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="position_pluses",
    )

    class Meta:
        verbose_name = "Plus por puesto"
        verbose_name_plural = "Plus por puesto"
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_period", "position"],
                name="positionplus_unique_per_period_position",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.position.name}: {self.amount} {self.currency.code}"


class PayrollEntry(TimestampedModel):
    """Liquidación de un empleado en una quincena."""

    payroll_period = models.ForeignKey(
        PayrollPeriod, on_delete=models.CASCADE,
        related_name="entries",
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        related_name="payroll_entries",
    )

    # Snapshot del empleado al momento de generar la entry (para auditoría).
    company_snapshot = models.CharField(max_length=120, blank=True)
    team_snapshot = models.CharField(max_length=200, blank=True)
    boss_snapshot = models.CharField(max_length=120, blank=True)
    position_snapshot = models.CharField(max_length=120, blank=True)
    primary_rubro_snapshot = models.CharField(max_length=120, blank=True)
    suspended = models.BooleanField(default=False, help_text="Suspendido en esta quincena puntual.")

    # Sueldo base
    value_jornal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    currency = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT,
        related_name="payroll_entries",
    )

    # Asistencia / ausencias
    days_worked = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    absences = models.DecimalField("Faltas", max_digits=5, decimal_places=2, default=Decimal("0"))
    justified_absences = models.DecimalField("Justificadas", max_digits=5, decimal_places=2, default=Decimal("0"))
    vacations = models.DecimalField("Vacaciones (días)", max_digits=5, decimal_places=2, default=Decimal("0"))
    vacations_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    vacations_detail = models.CharField(max_length=200, blank=True)

    # Horas
    late_hours = models.DecimalField("H. tarde", max_digits=5, decimal_places=2, default=Decimal("0"))
    late_hours_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    late_hours_detail = models.CharField(max_length=200, blank=True)
    overtime_hours = models.DecimalField("H. extra", max_digits=5, decimal_places=2, default=Decimal("0"))
    overtime_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))

    # Subtotales (calculados en save())
    attendance_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    hours_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    extraordinary_subtotal = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"),
        help_text="Suma de extraordinarios (Turno C).",
    )
    presentismo_subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    gross = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))

    # Pago
    net = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    bank_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))
    cash_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))

    # Conteo de billetes (calculado por defecto desde cash_amount, editable).
    bills_1000 = models.PositiveIntegerField(default=0)
    bills_500 = models.PositiveIntegerField(default=0)
    bills_200 = models.PositiveIntegerField(default=0)
    bills_100 = models.PositiveIntegerField(default=0)
    bills_50 = models.PositiveIntegerField(default=0)
    bills_20 = models.PositiveIntegerField(default=0)
    bills_10 = models.PositiveIntegerField(default=0)
    bills_manual_override = models.BooleanField(
        default=False,
        help_text="Si está marcado, no recalcular los billetes desde cash_amount.",
    )

    # Comentarios
    receipt_observations = models.CharField(max_length=300, blank=True,
                                             help_text="Aparece en el recibo.")
    internal_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Entrada de quincena"
        verbose_name_plural = "Entradas de quincena"
        ordering = ("payroll_period", "employee_id")
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_period", "employee"],
                name="payrollentry_unique_employee_per_period",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} @ {self.payroll_period}"

    # ----- Cálculos -----

    def recalculate(self) -> None:
        """Recalcula subtotales, neto y conteo de billetes. NO guarda."""
        period = self.payroll_period
        jornal = self.value_jornal or Decimal("0")

        # Asistencia: días × jornal.
        self.attendance_subtotal = (self.days_worked * jornal).quantize(Decimal("0.01"))

        # Plus por puesto: position_plus.amount × días, si hay para el puesto.
        plus_position_total = Decimal("0")
        if self.employee.position_id:
            plus = (
                period.position_pluses
                .filter(position_id=self.employee.position_id)
                .first()
            )
            if plus is not None:
                plus_position_total = (plus.amount * self.days_worked).quantize(Decimal("0.01"))

        # Horas extra: overtime × valor_hora × (1 + plus_overtime_pct/100).
        hours_per_day = Decimal(period.hours_weekday or 8)
        valor_hora = jornal / hours_per_day if hours_per_day else Decimal("0")
        ot_multiplier = Decimal("1") + (period.plus_overtime_pct or Decimal("0")) / Decimal("100")
        self.overtime_amount = (self.overtime_hours * valor_hora * ot_multiplier).quantize(Decimal("0.01"))

        self.hours_subtotal = (self.overtime_amount - self.late_hours_amount).quantize(Decimal("0.01"))

        # Bruto (sin presentismo ni extraordinarios).
        self.gross = (
            self.attendance_subtotal
            + plus_position_total
            + self.overtime_amount
            - self.vacations_amount
            - self.late_hours_amount
        ).quantize(Decimal("0.01"))

        # Presentismo: pct sobre el bruto.
        pres_pct = (period.plus_presentismo_pct or Decimal("0")) / Decimal("100")
        self.presentismo_subtotal = (self.gross * pres_pct).quantize(Decimal("0.01"))

        # extraordinary_subtotal lo setea el Turno C cuando existan; queda como está.

        # Neto = bruto + presentismo + extraordinarios; redondeo a múltiplo de 10.
        net_raw = self.gross + self.presentismo_subtotal + self.extraordinary_subtotal
        self.net = round_to_multiple_of_10(net_raw)

        # Si bank + cash != net, ajustar cash con la diferencia (Turno C/D
        # afinará esto vía OrganizationPayrollSettings).
        if (self.bank_amount or Decimal("0")) + (self.cash_amount or Decimal("0")) != self.net:
            self.cash_amount = self.net - (self.bank_amount or Decimal("0"))
            if self.cash_amount < 0:
                self.cash_amount = Decimal("0")

        # Billetes desde cash_amount, salvo override manual.
        if not self.bills_manual_override:
            cash = int(self.cash_amount or 0)
            bills, _remainder = calculate_bills(cash)
            self.bills_1000 = bills[1000]
            self.bills_500 = bills[500]
            self.bills_200 = bills[200]
            self.bills_100 = bills[100]
            self.bills_50 = bills[50]
            self.bills_20 = bills[20]
            self.bills_10 = bills[10]

    def save(self, *args, **kwargs):
        # Tomar snapshots la primera vez.
        if self._state.adding:
            self._take_snapshot()
        self.recalculate()
        super().save(*args, **kwargs)
        # Cache del último jornal en el empleado.
        if self.value_jornal:
            Employee.objects.filter(pk=self.employee_id).update(
                last_known_salary=self.value_jornal,
                last_known_currency_id=self.currency_id,
            )

    def _take_snapshot(self) -> None:
        emp = self.employee
        if emp.company_id and not self.company_snapshot:
            self.company_snapshot = emp.company.name
        if emp.position_id and not self.position_snapshot:
            self.position_snapshot = emp.position.name
        if emp.boss_id and not self.boss_snapshot:
            try:
                self.boss_snapshot = emp.boss.full_name
            except Exception:
                self.boss_snapshot = ""
        if emp.primary_rubro_id and not self.primary_rubro_snapshot:
            self.primary_rubro_snapshot = emp.primary_rubro.name
        if not self.team_snapshot:
            self.team_snapshot = ", ".join(t.name for t in emp.teams.all())


def pre_generate_entries_for_period(period: PayrollPeriod, default_currency=None) -> list[PayrollEntry]:
    """Crea PayrollEntry stubs para cada empleado activo de la sociedad.

    Si ya existen entradas no las duplica. value_jornal arranca con el
    last_known_salary del empleado para que sea fácil iterar.
    """
    from apps.currencies.models import Currency

    if default_currency is None:
        default_currency = Currency.objects.get(code="ARS")

    existing_employee_ids = set(period.entries.values_list("employee_id", flat=True))
    active_employees = (
        period.company.employees
        .filter(termination_date__isnull=True)
        .exclude(pk__in=existing_employee_ids)
    )

    created = []
    for emp in active_employees:
        entry = PayrollEntry(
            payroll_period=period,
            employee=emp,
            currency=emp.last_known_currency or default_currency,
            value_jornal=emp.last_known_salary or Decimal("0"),
            days_worked=Decimal(period.total_days or 0),
        )
        entry.save()
        created.append(entry)
    return created
