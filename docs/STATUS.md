# Mamsys V.1 — Estado del proyecto

> Documento de estado a alto/medio nivel: qué se construyó, cómo funciona,
> qué falta. Última actualización: post-Fase 11 (framework de importadores).

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Commits en `main` | 24 |
| Apps Django | 17 |
| Modelos persistidos | ~45 |
| Tests automatizados | **173 pasando** |
| Líneas de Python en apps/ | ~10.000 |
| Fases del SPEC completas | **11/11** + framework de importadores |

**Lo que el sistema hace hoy** (end-to-end, todo testeado):

1. Una constructora crea su organización vía sign-up público → tenant aislado en su propio schema de Postgres.
2. Carga sus sociedades (S.A., S.R.L., Monotributo), catálogos (rubros, materiales, proveedores, puestos, etc.), obras y empleados.
3. Configura cotizaciones (BNA, CCL, 70/30) y carga precios.
4. Define maestros: tareas y mezclas con recetas recursivas. El sistema calcula su costo automáticamente desde precios + último jornal.
5. Carga compras (con o sin ítems) → el sistema actualiza precios automáticamente y deja la compra en la bandeja "A pagar" de Tesorería.
6. Tesorería registra pagos → status de compra se actualiza solo → se crea un movimiento en Tesorería automáticamente.
7. RRHH crea quincenas → el sistema pre-genera entradas para cada empleado activo y calcula todo (bruto, presentismo, neto redondeado, billetes). Cada empleado se imputa N obras con %.
8. Tesorería carga la Carga Social del mes → se prorratea automáticamente entre los empleados y sus imputaciones a obras.
9. Se arman presupuestos versionados (P1/P2/P3) que congelan precios y recetas al aprobarse.
10. Cruce Presupuesto vs Real: ¿cuánto llevo gastado vs lo que planifiqué? Por categoría, rubro y tarea.
11. Seguimiento por obra: snapshot del día con KPIs + análisis de varianzas que detecta tareas mal estimadas en el maestro y sugiere ajustes.
12. Importador CSV/Excel para migrar planillas existentes de Sheets.

---

## 2. Arquitectura general

### Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12 (brew) |
| Framework | Django 5.2 |
| API | Django REST Framework (instalado, sin endpoints aún) |
| Base de datos | PostgreSQL 16 (brew, en local sin password con trust auth) |
| Multi-tenancy | django-tenants (schema-por-organización) |
| Auth | django-allauth + custom User con email como USERNAME_FIELD |
| Permisos | django-rules + modelo Role propio (configurable por org) |
| Tareas async | Celery + Redis (instalado, sin tareas async todavía) |
| Frontend | Tailwind CSS (via CDN en dev) + HTMX + Alpine.js |
| PDF | WeasyPrint (instalado, sin uso aún) |
| Excel | openpyxl (usado por imports) |
| Tests | pytest + pytest-django + factory-boy |
| Hosting local | Postgres + Redis vía brew services |

### Multi-tenancy

- **Schema `public`** (compartido — SHARED_APPS):
  - `organizations.Organization` (tenant de django-tenants)
  - `organizations.Domain` (subdomain → tenant)
  - `organizations.Membership` (user ↔ org con role)
  - `organizations.Invitation`
  - `accounts.User` (email único global)
  - `permissions.Role` (rol por organización con lista de permission codes)
  - `permissions.ObjectAccess` (acceso fino por objeto)
  - `currencies.Currency` (ARS/USD/EUR — globales del SaaS)

- **Schema por tenant** (TENANT_APPS): cada organización tiene su propio schema con todas sus apps de negocio. `demo` es el tenant de prueba en local.

- **Resolución de tenant**: por dominio. `localhost` → tenant `public`, `demo.localhost` → tenant `demo`. En producción cada cliente tendría su subdomain (`pasfas.mamsys.com.ar`).

### Layout del repo

```
mamsys-V.1/
├── apps/                        # 17 apps Django
│   ├── core/                    # Modelos abstractos (Timestamped, CatalogItem), AuditLog
│   ├── accounts/                # User custom + tokens
│   ├── organizations/           # Tenants, Domain, Membership, Invitation
│   ├── permissions/             # Role, ObjectAccess, constants
│   ├── currencies/              # Currency (SHARED) + seed ARS/USD/EUR
│   ├── catalog/                 # 14 catálogos vía factory de URLs/views
│   ├── companies/               # Sociedades (per-tenant)
│   ├── projects/                # Obras (Project)
│   ├── pricing/                 # ExchangeRateType, ExchangeRate, Price polimórfico
│   ├── procurement/             # Purchase, PurchaseItem, PurchasePayment
│   ├── payroll/                 # Employee + Quincenas + CS
│   ├── task_master/             # Mix, Task con componentes recursivos
│   ├── budgets/                 # Budget versionado + BudgetItem con snapshot
│   ├── budget_analysis/         # Cruce Presupuesto vs Real
│   ├── treasury/                # TreasuryEntry + signals
│   ├── tracking/                # Snapshots + TaskExecution + VarianceAnalyzer
│   └── imports/                 # Framework genérico de importadores
├── mamsys/                      # Config del proyecto (settings split, urls, celery)
├── templates/                   # Base + partials reutilizables
├── docs/
│   ├── SPEC.md                  # Especificación funcional (fuente de verdad)
│   └── STATUS.md                # Este documento
├── requirements/                # base.txt, dev.txt, prod.txt
├── docker-compose.yml           # Postgres 16 + Redis 7 (no se usa en local con brew)
├── manage.py
├── pyproject.toml               # ruff, pytest, coverage
└── README.md
```

### Decisiones de arquitectura no triviales

1. **Currency es SHARED, ExchangeRateType es TENANT.** Las monedas son globales (USD es USD), pero cada org configura sus tipos de cotización (BNA, CCL, Nocito, 70/30).
2. **Role es SHARED**, con FK a Organization. Decisión pragmática para no tener FK cross-schema desde Membership.
3. **Sin FK cross-schema**: para tareas que apuntan a TENANT desde SHARED se usa `GenericForeignKey` (caso de `Price.item`).
4. **`PurchaseItem.task_id` y `PayrollAllocation.task_id` son enteros sin FK** (placeholder hasta que se cargue Task — para evitar dependencias circulares en migraciones). Cuando un usuario los carga, el cruce vs Budget y los snapshots ya leen ese id.
5. **Snapshots por inmutabilidad**: presupuestos aprobados, quincenas cerradas y CS prorrateadas se "congelan" persistiendo el cálculo. Cambios posteriores en catálogos no los afectan.
6. **Signals para automatización**:
   - `PurchaseItem.save()` (en compra confirmada) → crea `Price`.
   - `PurchasePayment.save()` → actualiza status de compra + crea `TreasuryEntry`.
   - `SocialChargesPayment.save()` → prorratea CS a allocations + crea `TreasuryEntry`.
   - `Purchase.save()` (transición a confirmada) → alimenta `Price` para items existentes.
   - `PayrollExtraordinary` / `PayrollAllocation` save → re-calcula la `PayrollEntry`.
7. **Factory de catálogos**: en `apps/catalog/views.py`, una sola entrada en el dict `CATALOGS` genera list/create/update views + URLs. 14 catálogos sin boilerplate repetido.

---

## 3. Apps en detalle

### 3.1 Apps base (Fase 1)

**`apps.core`** — abstracciones
- `TimestampedModel`: created_at, updated_at, created_by, updated_by. Toda app de negocio hereda.
- `CatalogItem`: nombre + code + active + order. Base para todos los catálogos.
- `AuditLog`: registro de cambios con JSON diff (placeholder, sin uso intensivo todavía).

**`apps.accounts`** — usuarios
- `User` custom (AbstractBaseUser + PermissionsMixin) con `email` como `USERNAME_FIELD`. `is_staff` reservado para super-admin del SaaS.
- Tokens de verificación de email y reset de password.
- Templates de allauth sobrescritos con estilo de Mamsys.

**`apps.organizations`** — tenancy
- `Organization` hereda de `TenantMixin` → cada save crea un schema en Postgres.
- `Domain` mapea host → tenant.
- `Membership` (user ↔ org con role + `is_active`).
- `Invitation` con token UUID y expiración.
- Signal `provision_default_roles` se dispara al crear Org → carga los 5 roles base.
- Servicio `signup_organization()` atómico: User + Org + Domain + EmailAddress (allauth) + Membership Admin.

**`apps.permissions`** — autorización
- `Role`: por organización, nombre, descripción, lista JSON de permission codes.
- `ObjectAccess`: GenericForeignKey con can_view/can_edit para gating por objeto.
- `constants.py`: 36 permission codes (VIEW_PROJECTS, EDIT_PURCHASES, etc.).
- 5 roles base: Admin (todos), Área Técnica, Tesorería, RRHH, Solo Lectura.
- Helper `user_has_permission(user, org, code)`.

### 3.2 Catálogos y entidades base (Fase 2)

**`apps.currencies`** (SHARED)
- `Currency`: code (ISO), name, symbol, active.
- Data migration que siembra ARS, USD, EUR.

**`apps.catalog`** — 14 modelos en una sola app
| Modelo | Notas clave |
|---|---|
| `Rubro` | name único |
| `Subrubro` | FK Rubro estricta; (rubro, name) único |
| `Unit` | symbol único, category (length/area/volume/weight/time/global) |
| `BusinessComponent` | clasificador transversal (TERRENO, VENTA UF) |
| `ProjectStatus` | Solo Terreno, En Construcción, Completada |
| `EmployeeStatus` | Activo/Suspendido/Renuncio/Despedido |
| `Position` | Ayudante/Medio Of./Oficial/RT/etc. |
| `Bank` | Galicia, Ciudad, etc. |
| `BankAccount` | bank + company + currency + account_number + cbu + alias |
| `Team` | name + leader (FK Employee opcional) |
| `Supplier` | code, category, M2M Rubros, contacto, CUIT |
| `Material` | rubro, subrubro opcional, unit, last_known_price |
| `Subcontract` | unit, typical_supplier opcional |
| `ExtraordinaryConcept` | name + type (income/expense), (type,name) único |
| `TrackingCategory` | name + color hex |

Todos los catálogos usan el **factory `CATALOGS`** en `apps/catalog/views.py` — agregar un nuevo catálogo es 1 entrada en el dict + 1 ModelForm.

**`apps.companies`** — Sociedades (Razones sociales)
- Per-tenant. Una org tiene N sociedades (PASFAS SA, 350 SRL, etc.).
- Campos: name, legal_name, tax_id (CUIT), iva_condition, iibb_number, fiscal_address.
- Wizard: cuando un Admin entra al tenant y no hay ninguna Sociedad, lo redirige al alta.

**`apps.projects`** — Obras
- Per-tenant. FK PROTECT a Company + opcional a ProjectStatus.
- name (+ unique por company), code (unique parcial), address, fechas (inicio/fin estimado/fin real), `project_manager` (FK User), notes, is_archived.
- UI: list con filtro archivadas, detail con tabs (Resumen / Compras / MO / Presupuestos / Seguimiento → este último activo, otros placeholder).

### 3.3 Pricing (Fase 3)

**`apps.pricing`**

- `ExchangeRateType`: name único, currency_from→currency_to, is_default, calculation_type (`manual` | `weighted_combination`), `combination_formula` JSON.
- `ExchangeRate`: rate_type + date (único combo) + rate (Decimal 15.4) + source (manual/imported/calculated).
- `Price` polimórfico: `GenericForeignKey` apunta a Material, Subcontract, Position, Mix o Task. amount, currency, effective_date, supplier opcional, source, `is_reference` flag, `source_purchase_item_id` para idempotencia con el signal de compras.

**Servicios:**
- `CurrencyConversionService.get_rate(rate_type, date)`: busca tasa exacta, sino la más cercana anterior dentro de 30 días, sino lanza `ExchangeRateNotFoundError`. **Para tipos calculados (70/30)**: resuelve recursivamente los componentes y persiste el resultado como ExchangeRate `source=calculated` (cache idempotente).
- `CurrencyConversionService.convert(amount, from, to, date, rate_type)`: maneja inversión cuando el tipo está en dirección opuesta.
- `PriceLookupService.get_current_price(item, currency, date, rate_type, strategy)`: 3 estrategias:
  - `most_recent` (default): el Price más reciente con `is_reference=True`.
  - `weighted_average_n_days`: promedio ponderado por recencia.
  - `min_n_days`: mínimo de la ventana.

**UI**: `/cotizaciones/` lista tipos con última tasa y default, detail con histórico de 60 días + form rápido para cargar la del día.

### 3.4 Compras (Fase 4)

**`apps.procurement`**

- `Purchase`: cabecera con `purchase_type` (obra/admin/cadeteria), `document_type` (FA/FB/FC/presupuesto/remito/ticket/otro), document_number, invoice_date, `is_subcontract`, `is_itemized` (auto), supplier+email, company, project (obligatorio si type=obra), rubro/subrubro/business_component, montos en moneda original (sin IVA, IVA 21/10.5, IIBB, total), original_currency, `exchange_rate_used` + cache de totales en ARS/USD oficial/USD CCL, payment_method, week_to_pay, due_date, status (draft/to_pay/paid_partial/paid/cancelled), warehouse (placeholder), notes.
- `PurchaseItem`: FK Purchase CASCADE, item_description, **XOR(material, subcontract)** validado en clean(), quantity, unit, unit_price, total (auto-calc), subrubro override, tracking_category, task_id placeholder.
- `PurchasePayment`: payment_date, amount, currency, exchange_rate_used opcional, payment_method, reference.

**Signals**:
- `PurchaseItem post_save` (en compra confirmada): upsert `pricing.Price` con `source_purchase_item_id` como ancla idempotente. Actualiza `Material.last_known_price` / `Subcontract.last_known_price`.
- `Purchase post_save` (transición a confirmada): alimenta Prices para items existentes.
- `PurchasePayment post_save/delete`: recalcula `Purchase.status` según suma de pagos (paid_partial/paid/to_pay).

**Funciones agregadas (Turno C)**:
- Lista con 8 filtros (buscar, tipo, estado, proveedor, obra, sociedad, desde, hasta) y 4 KPIs.
- Bandeja "A pagar" agrupada por week_to_pay con saldos.
- Cuenta corriente por proveedor con saldo pendiente.

### 3.5 Nómina (Fase 5 — 4 turnos)

**`apps.payroll`**

| Modelo | Función |
|---|---|
| `Employee` | datos laborales: company, status, position, teams M2M, boss self-FK, primary_rubro, hire/termination_date, arca_registered |
| `EmployeePersonalData` (1-a-1) | nombre, documento, CUIL, nacimiento, estado civil, contacto |
| `EmployeeBanking` (1-a-1) | bank, cbu, cvu_mercado_libre |
| `EmergencyContact` (1-N) | full_name, relationship, phone |
| `PayrollPeriod` | quincena por sociedad: period_number, month, year, fechas, días/horas, plus generales (overtime%, presentismo%), status (open/closed/paid) |
| `PositionPlus` | adicional por puesto/quincena |
| `PayrollEntry` | empleado-en-quincena con snapshots (puesto/equipo/jefe), value_jornal, asistencia, horas, subtotales calculados, neto redondeado, banco/efectivo, billetes 7 denominaciones |
| `PayrollAllocation` | imputación a N obras con pct (suma = 100), jornal/net/CS amounts, social_charges_status (estimated/real) |
| `PayrollExtraordinary` | bonos/adelantos/etc. con FK ExtraordinaryConcept |
| `SocialChargesPayment` | pago de CS por sociedad/mes |

**Cálculos automáticos (`PayrollEntry.recalculate`)** — siguiendo SPEC §9.2:
```
attendance_subtotal = days_worked × value_jornal
position_plus_total = (PositionPlus del puesto) × días
overtime_amount = horas_extra × (jornal/hours_weekday) × (1 + plus_overtime_pct/100)
extraordinary_subtotal = suma firmada de extraordinarios (income - expense)
gross = attendance + position_plus + overtime - vacations - late_hours_amount
presentismo = gross × plus_presentismo_pct/100
net = round10(gross + presentismo + extraordinary)
cash = net - bank (no-negative)
billetes = greedy con [1000, 500, 200, 100, 50, 20, 10] (salvo override manual)
```

**Servicios**:
- `pre_generate_entries_for_period(period)`: crea entrys stub para empleados activos de la sociedad. Idempotente.
- `SocialChargesProrateService.prorate(payment)`: distribuye el monto de CS proporcional al bruto de cada empleado del mes y luego según pct de allocation. Marca `social_charges_status='real'`. Idempotente.

**Signals**: cualquier cambio en `PayrollExtraordinary` o `PayrollAllocation` re-guarda la entry, que dispara `recalculate()` en cascada.

### 3.6 Maestros (Fase 6)

**`apps.task_master`**

- `Mix`: receta de mezcla con name único, output_unit, version, active.
- `MixComponent`: XOR(material, sub_mix) + quantity_per_unit + input_unit. clean() detecta ciclos.
- `Task`: tarea maestra con code jerárquico opcional, rubro, subrubro, output_unit, version.
- `TaskComponent`: 5 source_types (material/labor/subcontract/sub_mix/sub_task). Exactamente un FK lleno. Auto-clasifica como materials o labor.
- `TaskAdjustmentSuggestion`: lo llena tracking en Fase 7.

**Detección de ciclos** (`validators.py`): DFS antes de guardar componentes con sub_mix o sub_task.

**`TaskCostCalculator.calculate(task_or_mix, currency, date, rate_type)`**:
- Material/subcontract → `PriceLookupService.get_current_price()` con fallback a `last_known_price`.
- Labor (Position) → último `value_jornal` de un PayrollEntry de empleados en ese puesto.
- sub_mix/sub_task → recurse.
- Devuelve `CostBreakdown` con materials/labor + componentes + sub_breakdowns navegables.

**UI**: `/maestros/` con landing → /tareas/ y /mezclas/. Editor inline con costo en vivo en el detalle. Sub-mezclas como `<details>` colapsables anidados.

### 3.7 Presupuestos (Fase 8)

**`apps.budgets`**

- `Budget`: project, name, version, status (draft/submitted/approved/rejected/superseded), snapshot al cerrar (pricing_date, exchange_rate_type, exchange_rate_value), totales (materials/labor/subcontracts/margin_pct/total_with_margin), approved_by/at.
- `BudgetItem`: FK Task + quantity + snapshot de unit_cost/total_cost/breakdown + `recipe_snapshot` (JSON con receta completa al momento).

**Servicios**:
- `BudgetCalculatorService.compute()`: en draft usa `TaskCostCalculator` (vivo); en estados cerrados lee snapshot.
- `BudgetSnapshotService.freeze()`: congela todo. Por cada item llama TaskCostCalculator, persiste unit_cost + breakdown + recipe_snapshot.
- `BudgetApprovalService`:
  - `submit()`: draft → submitted, dispara freeze.
  - `approve()`: freeze si no estaba, marca aprobaciones previas como superseded.
  - `reject()`: → rejected.
  - `clone_as_new_version()`: crea P{n+1} draft copiando items.

**UI**: `/presupuestos/` con filtros, alta con inline formset, detail con KPIs + acciones contextuales (Presentar/Aprobar/Rechazar/Nueva versión) + banner 🔒 cuando is_locked.

### 3.8 Cruce vs Real (Fase 9)

**`apps.budget_analysis`**

- `BudgetVsActualReport`: persiste el resultado del cruce con totales y data JSON.

**`BudgetActualCrossService.compute(budget, cutoff_date, currency, rate_type)`**:
- Planned: lee snapshot del Budget (materials_cost, labor_cost, subcontracts_cost) y total por BudgetItem.
- Actual:
  - Compras hasta `cutoff_date` excluyendo canceladas. Por compra con ítems, prorratea total c/IVA según subtotal de items. `is_subcontract` → bucket subcontracts; sino materials. Group by rubro y task (cuando hay link).
  - Nómina: PayrollAllocation cuyo `payroll_period.end_date ≤ cutoff_date`. Suma `net_amount + social_charges_amount` al bucket labor.
- Conversión multi-moneda automática vía CurrencyConversionService.

**UI**: `/presupuesto-vs-real/`. Form pide budget + cutoff + moneda + rate_type + checkbox "Guardar reporte". Vista previa al vuelo o reporte persistido. Breakdown por categoría / rubro / tarea con varianzas coloreadas (rojo positivo = pasaste el presupuesto).

### 3.9 Tesorería (Fase 10)

**`apps.treasury`**

- `TreasuryEntry`: entry_type (income/expense/transfer/currency_exchange), category (10 valores: supplier_payment, payroll_payment, social_charges_payment, taxes, financing, admin, client_payment, client_advance, transfer, currency_exchange, other), date, company, bank_account (null → efectivo), counterpart_account, amount + currency, multi-moneda con exchange_rate_used + counterpart_amount/currency, project opcional, 3 OneToOne a sources (purchase_payment, social_charges_payment, payroll_period), is_reconciled + reconciled_at/by.

**Signals automáticas**:
- `PurchasePayment` → upsert TreasuryEntry expense/supplier_payment.
- `SocialChargesPayment` → upsert TreasuryEntry expense/social_charges_payment.
- Ambos con delete cascade.

**`compute_account_balances(cutoff_date, company_id)`**: saldo = ingresos − egresos por bank_account, agrupando entries sin cuenta como "Efectivo (moneda)".

**UI**: `/tesoreria/` con 8 filtros + KPIs + toggle de conciliación inline. `/tesoreria/saldos/` con balance por cuenta. Alta manual de movimientos.

### 3.10 Seguimiento (Fase 7)

**`apps.tracking`**

- `ProjectExecutionSnapshot`: foto por fecha con totals (materials/labor/subcontracts/CS real+estimado), breakdown JSON. Unique (project, snapshot_date).
- `TaskExecution`: planned_quantity/cost (del último Budget approved) vs actual_quantity/cost (acumulado de PurchaseItems con task_id + PayrollAllocations con task_id), variance properties.
- `ProjectForecast`: placeholder para forecasting futuro.

**`TrackingService.snapshot_project(project, date)`**: agrega compras + nómina hasta la fecha, persiste el snapshot (idempotente por fecha) y llama `update_task_executions()` que cruza con el último Budget approved.

**`VarianceAnalyzer.scan(threshold_pct, min_samples)`**: agrupa TaskExecutions por task; si ≥N obras tienen varianza promedio > umbral, crea/actualiza `TaskAdjustmentSuggestion PENDING`.

**`approve_suggestion()` / `reject_suggestion()`**: aprobar incrementa `Task.version` del maestro.

**UI**: `/seguimiento/obras/<pk>/` con snapshot del día + tabla de TaskExecutions con varianza coloreada + historial. `/seguimiento/sugerencias/` con botón "Escanear varianzas" y acciones Aprobar/Rechazar.

### 3.11 Importadores (Fase 11 — primera entrega)

**`apps.imports`**

- `ImportLog`: persiste cada importación (status, stats, errors JSON, user).
- `BaseImporter`: parse CSV/XLSX, valida required columns, llama hook `process_row(row, dry_run)` por fila. Captura `ValueError` como error de fila. Las filas con error NO se persisten.
- 3 importadores concretos: `RubroImporter`, `SubrubroImporter`, `MaterialImporter`.
- Encoding/separador autodetect (UTF-8/Latin-1, coma/punto-y-coma).

**UI**: `/importadores/` con grilla de importadores → upload → preview (con KPIs + errores por fila + muestra de 20 acciones) → confirmar → log persistido.

---

## 4. Cómo se conectan (flujo de datos)

### Flujo "carga una compra de obra"
```
Usuario crea Purchase → confirma (status=to_pay)
    ↓
PurchaseItem.save() ───→ signal sync_price_from_item
    ↓                         ↓
                          pricing.Price (upsert idempotente)
                              ↓
                          Material.last_known_price (cache)
    ↓
PurchasePayment.save() ──→ signal create_entry_for_purchase_payment
    ↓                         ↓
update_purchase_payment_status  treasury.TreasuryEntry (upsert)
    ↓
Purchase.status = paid_partial/paid según suma
```

### Flujo "quincena con CS"
```
PayrollPeriod.save() → pre_generate_entries_for_period
    ↓
Por cada Employee activo:
    PayrollEntry stub (jornal del último, días totales)
    ↓
Usuario edita entry (jornal, días, horas, etc.)
    ↓
PayrollEntry.recalculate() corre desde save():
    - lee PayrollExtraordinaries → extraordinary_subtotal
    - calcula attendance, overtime, presentismo, gross, net
    - distribuye gross/net a PayrollAllocations según pct
    - calcula billetes desde cash_amount
    ↓
Tesorería carga SocialChargesPayment
    ↓
Signal SocialChargesProrateService.prorate:
    - calcula pct_employee = entry.gross / total_gross_mes
    - asigna CS a cada Allocation según su pct
    - marca social_charges_status='real'
    ↓
Signal create_entry_for_social_charges → treasury.TreasuryEntry
```

### Flujo "presupuesto vs real"
```
Budget(draft) con BudgetItems → costos calculados en vivo via TaskCostCalculator
    ↓
submit() o approve() → BudgetSnapshotService.freeze()
    - congela pricing_date, exchange_rate_value
    - por cada item: persiste unit_cost, breakdown, recipe_snapshot JSON
    ↓
Tiempo pasa, se cargan Compras + Quincenas
    ↓
Usuario corre Cruce vs Real → BudgetActualCrossService.compute()
    - Planned ← snapshot del Budget
    - Actual ← Compras + PayrollAllocations hasta cutoff_date
    - Group by categoria/rubro/task (cuando hay task_id link)
    - Conversión multi-moneda automática
    - Devuelve CrossResult navegable
    ↓
Si "Guardar" → BudgetVsActualReport con data JSON
```

---

## 5. Lo que funciona end-to-end (probado)

✅ **Sign-up de organización** → crea schema en Postgres + Domain + 5 roles base + Membership Admin del primer user.

✅ **Login multi-tenant** → cada subdominio tiene su sesión (`localhost` vs `demo.localhost`).

✅ **Wizard de Sociedad** → cuando el tenant entra y no hay Company, lo redirige a alta.

✅ **CRUD de los 14 catálogos** vía factory genérico.

✅ **Cotizaciones**: alta manual + tipos calculados 70/30 que resuelven recursivo y cachean resultado.

✅ **Compras**: cabecera + items + pagos. Signal popula Price automáticamente. Status sigue suma de pagos.

✅ **Bandeja A pagar** agrupada por semana, Cuenta corriente por proveedor.

✅ **Quincenas**: pre-gen de entradas, recalcular automático, billetes greedy, allocations con suma 100, extraordinarios firmados, CS con prorrateo automático.

✅ **Maestros**: editor con costo en vivo, recursivos hasta cualquier profundidad (con detección de ciclos), 5 source_types con validación XOR.

✅ **Presupuestos**: versionado P1/P2/P3 con snapshot al cerrar, supersedencia automática, clone para iterar.

✅ **Cruce Presupuesto vs Real**: agrega compras + nómina, conversión multi-moneda, breakdown por categoría/rubro/task.

✅ **Tesorería**: signals automáticas desde compras/CS, saldos por cuenta, conciliación 1-click, filtros completos.

✅ **Seguimiento**: snapshots agregados, TaskExecutions vs Budget, VarianceAnalyzer que sugiere ajustes al maestro.

✅ **Importadores**: framework + 3 concretos (Rubro/Subrubro/Material) con preview, errores por fila, log persistido.

---

## 6. Métricas de tests por app

| App | Tests | Coverage del flujo |
|---|---|---|
| accounts | 3 | UserManager, normalización, validaciones |
| organizations | 4 | signup service + form validation |
| permissions | 4 | constants, roles |
| catalog | 9 | constraints únicos, FK |
| companies | 3 | modelos básicos |
| projects | 5 | str, unique, FK |
| currencies | 1 | seed |
| pricing | 23 | conversión, fallback, calculados, lookup con 3 estrategias |
| procurement | 19 | XOR, totales, signal Compra→Price, pagos, conversión multi-moneda |
| payroll | 46 | recalculate paths, billetes, allocations 100%, extraordinarios, CS prorrateo |
| task_master | 15 | XOR, ciclos, recursivo calc, fallback last_known_price |
| budgets | 7 | live vs snapshot, freeze, approve+supersede, clone |
| budget_analysis | 7 | edge cases, cutoff, cancelled, varianza pos |
| treasury | 6 | signals upsert idempotente, balances |
| tracking | 10 | snapshot, idempotencia, planned desde Budget, VarianceAnalyzer |
| imports | 11 | dry-run, dedup, validaciones cross-FK |
| **TOTAL** | **173** | |

---

## 7. Lo que falta (pulido y producción)

### Pulido funcional

| Pieza | Esfuerzo | Valor |
|---|---|---|
| Más importadores: Supplier, Employee, Cotizaciones | bajo | alto |
| Importador Compras históricas (cabecera+items en CSV) | medio | alto |
| Importador Quincenas históricas | medio | medio |
| PDF de Presupuesto (WeasyPrint) | medio | alto |
| PDF Talonarios de quincena (recibos por empleado) | medio | alto |
| PDF Listado por banco (transferencias del mes) | bajo | medio |
| Dashboard real con KPIs por rol (hoy es placeholder) | medio | medio |
| Cuenta corriente proveedor multi-moneda | bajo | medio |
| Saldos de tesorería con conversión a una moneda elegida | bajo | medio |

### Pulido técnico

| Pieza | Esfuerzo | Valor |
|---|---|---|
| Permisos finos aplicados en views (decoradores) | medio | alto |
| Filtrado de sidebar según rol del usuario | bajo | alto |
| Tailwind compilado (sacar CDN para prod) | bajo | alto |
| Vendoreado de HTMX/Alpine (sacar CDN) | bajo | alto |
| Static files compression + WhiteNoise | bajo | medio |
| Tests de views (hoy solo unit tests + servicios) | medio | medio |
| Tests de signals con transaction=True | bajo | medio |
| Onboarding wizard al crear org (preseed catálogos mínimos) | medio | medio |

### Faltantes del SPEC que aún no entrega

- Conversión `task_id` placeholder → FK real a `task_master.Task` en `PurchaseItem` y `PayrollAllocation` (hoy se guarda como int sin FK).
- UI para editar la receta de un Task **al aprobar una sugerencia** (hoy solo bumpea version sin cambiar componentes).
- Forecasting real en `ProjectForecast` (modelo está, lógica no).
- Reportes guardados de exportación a Excel (Cash Flow, Base MO, etc.) — la base existe en servicios pero faltan los endpoints de descarga.
- Templates HTML separados para impresión.

### Infra / deploy

- Pipeline CI (GitHub Actions con pytest).
- Dockerfile + docker-compose para prod.
- Backup automático del schema de cada tenant.
- Variables sensibles en secrets manager.
- Rate limiting más estricto + logs estructurados.
- Sentry para errores.
- Healthcheck endpoint.

### Comercial

- Pricing y billing (plan por org, integración Stripe/MercadoPago).
- Trial period.
- Marketing site público (hoy solo hay una landing minimalista).

---

## 8. Cómo correr todo en local

Ver [README.md](../README.md) para la instalación inicial. Hoy con Postgres + Redis + venv ya configurados:

```bash
cd /Users/ripio/Documents/saas/mamsys-V.1
.venv/bin/python manage.py runserver
```

URLs:
- http://localhost:8000/ — landing del SaaS.
- http://demo.localhost:8000/ — tenant Demo (login: `mateo@demo.com` / `ContraseñaLarga123`).
- http://localhost:8000/admin/ — admin de plataforma (necesita superuser).

Tests:
```bash
.venv/bin/pytest        # full suite ~2min
.venv/bin/pytest apps/budgets/  # un solo dominio
```

---

## 9. Decisiones del SPEC §11 (aún a confirmar formalmente)

El SPEC tiene 13 supuestos default; el código los respeta pero el dueño aún no los firmó explícitamente:

1. N obras por quincena (no limitado a 2) ✓ implementado
2. Suma de jornales = bruto con tolerancia ✓
3. Conteo de billetes automático con override ✓
4. Moneda de sueldos ARS por defecto ✓
5. No emitir recibos legales (solo operativos) — pendiente confirmar
6. Compras alimentan precios automáticamente ✓
7. Más reciente con is_reference=True como default de PriceLookup ✓
8. Catálogo Subcontract separado de Material ✓
9. Subcontrato por compra entera, no por ítem ✓
10. Cálculo 70/30 automático ✓
11. "Nocito" como tipo custom de cotización ✓ (se asume cambista)
12. Cotización ausente → anterior más cercana dentro de 30 días ✓
13. Asistencia incluye días/faltas/justificadas/vacaciones/late/overtime ✓

---

## 10. Próximas decisiones

Cuando retomemos, las tres direcciones más útiles:

**A. Importadores reales** — sumar Supplier, Employee, Cotizaciones, y especialmente Compras históricas. Esto destraba el uso real con la data de Sheets que ya tenés.

**B. PDFs** — presupuesto profesional impresible (lo que el cliente final quiere ver), talonarios de quincena (lo que firma el operario al cobrar). Habilita venta y operativa real.

**C. Permisos finos + UX de roles** — para que el sistema pueda usarlo un equipo mixto sin que Tesorería rompa cosas de Gestión.

Cualquiera de las tres es ~1 sesión.
