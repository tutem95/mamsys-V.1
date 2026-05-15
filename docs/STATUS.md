# Mamsys V.1 — Estado del proyecto

> Snapshot exhaustivo del estado del proyecto al **2026-05-15**. Pensado como
> documento de handoff: si tenés que levantar esto en otra máquina (o si Claude
> retoma en una sesión nueva), todo lo necesario para no perder contexto está acá.

---

## 0. Contexto rápido

**Mamsys V.1** es un SaaS multi-tenant (Django + django-tenants) para constructoras pyme argentinas. Reemplaza un ecosistema de Google Sheets que el dueño venía usando: compras (KPS), nómina (MO), obras, presupuestos, multi-moneda (ARS/USD con BNA/CCL/70-30), tesorería y reportes.

- **Repo**: https://github.com/tutem95/mamsys-V.1 (rama `main`)
- **Dueño/usuario**: Mateo Monsegur (mateo.monsegur@ripio.com). Git identity local: `mateomonsegur@gmail.com` / `Mateo Monsegur`.
- **Idioma de trabajo**: español. UI también en español, URLs kebab-case (`/obras/`, `/compras/`, `/quincenas/`).
- **Paleta UI**: primary `#3d85c6`, secondary `#9fc5e8`, soft bg `#d0e2f3`. Tipografía Inter. Fondo blanco.
- **Producto comercial** (no interno) — pensado para vender a otras constructoras.

### Estado de implementación

| Métrica | Valor (2026-05-15) |
|---|---|
| Commits en `main` | 30 |
| Apps Django | 17 |
| Modelos persistidos | ~45 |
| Tests automatizados | **215 pasando** (`pytest -q` ~7 min) |
| Fases del SPEC | **11/11** completas + pulido en curso |
| Importadores | **9** (Rubro, Subrubro, Material, Supplier, Employee, ExchangeRate, Purchase, Unit, PayrollPeriod) |
| PDFs operativos | **2** (Presupuesto, Talonarios de quincena) |
| Permisos finos | **aplicados** a list views de negocio + sidebar filtrado por rol |

---

## 1. Cómo levantar todo desde cero en otra Mac (Apple Silicon)

Asumiendo macOS sin nada instalado.

### 1.1 Dependencias del sistema (Homebrew)

```bash
# Homebrew si no está
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Postgres 16 + Redis 8 + Python 3.12
brew install postgresql@16 redis python@3.12

# Levantar servicios
brew services start postgresql@16
brew services start redis

# Postgres queda en /opt/homebrew/opt/postgresql@16/bin (no se agrega al PATH).
# Para usar createdb/psql:
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

> **OJO con Python**: el instalador oficial de python.org tira errores SSL/certs con allauth en macOS. Usar Python 3.12 de brew (`/opt/homebrew/bin/python3.12`).

### 1.2 Base de datos

```bash
# Crear rol y DB. Sin password (trust auth en localhost).
createuser mamsys
createdb -O mamsys mamsys
```

`pg_hba.conf` viene con `trust` para localhost por defecto en brew. Si no, en `/opt/homebrew/var/postgresql@16/pg_hba.conf` asegurate de tener:
```
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

### 1.3 Clonar el repo

```bash
mkdir -p ~/Documents/saas && cd ~/Documents/saas
git clone https://github.com/tutem95/mamsys-V.1.git
cd mamsys-V.1
```

> **GitHub auth**: el PAT que usamos en esta máquina fue compartido en el chat y debe revocarse. En la otra máquina creá uno nuevo en https://github.com/settings/tokens (scope: `repo`) o configurá SSH.

### 1.4 venv + dependencias

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
```

`requirements/base.txt` tiene Django 5.2, django-tenants, allauth, rules, DRF, weasyprint, openpyxl. `dev.txt` agrega pytest + factory-boy + django-debug-toolbar.

### 1.5 Variables de entorno

```bash
cp .env.example .env
# El default ya funciona en local con la DB mamsys/mamsys/sin password.
# Generar SECRET_KEY si querés:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Contenido típico de `.env`:
```
DJANGO_SETTINGS_MODULE=mamsys.settings.dev
SECRET_KEY=<algún string largo random>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,.localhost
DATABASE_URL=postgres://mamsys:mamsys@localhost:5432/mamsys
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@mamsys.local
TENANT_BASE_DOMAIN=localhost
```

### 1.6 Migraciones y datos iniciales

```bash
# IMPORTANTE: django-tenants usa migrate_schemas, NO migrate.
.venv/bin/python manage.py migrate_schemas --shared

# Crear superuser de la plataforma (para /admin/ en public).
.venv/bin/python manage.py createsuperuser
# Usar mateo.monsegur@ripio.com / lo que quieras

# Crear el tenant 'public' (landing del SaaS) — solo la primera vez.
.venv/bin/python manage.py shell <<'PY'
from apps.organizations.models import Organization, Domain
pub, _ = Organization.objects.get_or_create(
    schema_name="public",
    defaults={"name": "Mamsys", "slug": "public"},
)
Domain.objects.get_or_create(domain="localhost", defaults={"tenant": pub, "is_primary": True})
PY

# Crear tenant demo + admin user.
.venv/bin/python manage.py shell <<'PY'
from django.utils.timezone import now
from apps.organizations.services import signup_organization
result = signup_organization(
    email="mateo@demo.com",
    password="ContraseñaLarga123",
    org_name="Demo Constructora",
    org_slug="demo",
    subdomain="demo",
)
print("OK:", result)
PY
```

`signup_organization()` (en `apps/organizations/services.py`) hace todo atómico: crea User + Organization + Domain + EmailAddress (allauth, verificada) + Membership Admin + provisiona los 5 roles base via signal.

### 1.7 Correr

```bash
.venv/bin/python manage.py runserver
```

URLs:
- http://localhost:8000/ — landing pública del SaaS (signup de nuevas orgs).
- http://demo.localhost:8000/ — tenant Demo. Login: `mateo@demo.com` / `ContraseñaLarga123`.
- http://localhost:8000/admin/ — admin Django para super-admin del SaaS.

macOS resuelve `*.localhost` a 127.0.0.1 automáticamente, no hace falta tocar `/etc/hosts`.

### 1.8 Tests

```bash
.venv/bin/pytest             # full ~7 min, debe dar 215 passed
.venv/bin/pytest apps/budgets/   # un dominio puntual
.venv/bin/pytest -x          # corta en el primer fallo
```

Si Postgres no está corriendo, los tests fallan con errores de conexión — `brew services list` para verificar.

---

## 2. Setup en Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y postgresql-16 redis-server python3.12 python3.12-venv build-essential libpq-dev
sudo systemctl enable --now postgresql redis-server

sudo -u postgres createuser mamsys
sudo -u postgres createdb -O mamsys mamsys
# Editar /etc/postgresql/16/main/pg_hba.conf: trust en local/127.0.0.1, restart.

# Resto idéntico a macOS desde 1.3
```

WeasyPrint en Linux necesita `libpango`, `libcairo`, `libgdk-pixbuf2.0`:
```bash
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0
```

---

## 3. Stack y decisiones de arquitectura

### Stack completo

| Capa | Tecnología | Notas |
|---|---|---|
| Lenguaje | Python 3.12 (brew) | 3.11 oficial daba problemas SSL |
| Framework | Django 5.2 | |
| API | Django REST Framework | instalado, sin endpoints |
| DB | PostgreSQL 16 | django-tenants requiere Postgres |
| Tenancy | django-tenants | schema-per-org |
| Auth | django-allauth | email como username |
| Permisos | rules (pkg PyPI) + Role propio | NO `django-rules`, ese paquete no existe |
| Tareas async | Celery + Redis | instalado, sin tareas todavía |
| Frontend | Tailwind CDN + HTMX + Alpine | falta compilar Tailwind para prod |
| PDF | WeasyPrint | 2 PDFs vivos |
| Excel | openpyxl + csv | imports |
| Tests | pytest + pytest-django + factory-boy | 215 tests |

### Multi-tenancy

- **Schema `public` (SHARED_APPS)**:
  - `organizations.Organization` (tenant django-tenants)
  - `organizations.Domain` (host → tenant)
  - `organizations.Membership` (User ↔ Org con Role + is_active)
  - `organizations.Invitation` (token UUID)
  - `accounts.User` (email único global)
  - `permissions.Role` (configurable por org, JSONField con permission codes)
  - `permissions.ObjectAccess` (GenericForeignKey para acceso fino)
  - `currencies.Currency` (ARS/USD/EUR — globales)

- **Schema por tenant (TENANT_APPS)**: 14 apps de negocio. Cada Organization tiene su propio schema en Postgres.

- **Resolución**: por dominio. `localhost` → public, `demo.localhost` → demo. En prod cada cliente tendría `<slug>.mamsys.com.ar`.

### Decisiones no triviales

1. **`Currency` es SHARED, `ExchangeRateType` es TENANT**: USD es USD globalmente, pero cada org configura sus tipos (BNA, CCL, Nocito, 70/30).
2. **`Role` es SHARED con FK a Organization**: pragmático para evitar FK cross-schema desde Membership.
3. **Sin FK cross-schema**: `Price.item` usa `GenericForeignKey`.
4. **`PurchaseItem.task_id` y `PayrollAllocation.task_id` son enteros sin FK** (placeholder). Razón: evitar dependencias circulares en migraciones. Cuando se asigna, el cruce vs Budget y los snapshots lo leen igual.
5. **Snapshots por inmutabilidad**: presupuestos aprobados, quincenas cerradas y CS prorrateadas se congelan persistiendo el cálculo. Cambios posteriores en catálogos no los afectan.
6. **Signals para automatización cross-app**:
   - `PurchaseItem.save()` (en compra confirmada) → upsert `Price` (idempotente por `source_purchase_item_id`).
   - `PurchasePayment.save()` → actualiza Purchase.status + crea TreasuryEntry.
   - `SocialChargesPayment.save()` → prorratea a allocations + crea TreasuryEntry.
   - `Purchase.save()` (transición a confirmada) → alimenta Prices para items existentes.
   - `PayrollExtraordinary` / `PayrollAllocation` save → recalcula `PayrollEntry`.
7. **Factory de catálogos**: `apps/catalog/views.py` tiene un dict `CATALOGS` — 1 entrada genera list/create/update views + URLs para los 14 catálogos.
8. **Custom User con email USERNAME_FIELD**: `is_staff` reservado para super-admin del SaaS; el poder en una org lo da el Role en Membership.

### Layout del repo

```
mamsys-V.1/
├── apps/                        # 17 apps Django
│   ├── core/                    # Modelos abstractos (Timestamped, CatalogItem), AuditLog, PDF render helper
│   ├── accounts/                # User custom + tokens
│   ├── organizations/           # Tenants, Domain, Membership, Invitation, signup service
│   ├── permissions/             # Role, ObjectAccess, constants, decorators, checks, templatetags
│   ├── currencies/              # Currency (SHARED) + seed ARS/USD/EUR
│   ├── catalog/                 # 14 catálogos vía factory de URLs/views
│   ├── companies/               # Sociedades (per-tenant)
│   ├── projects/                # Obras (Project)
│   ├── pricing/                 # ExchangeRateType, ExchangeRate, Price polimórfico
│   ├── procurement/             # Purchase, PurchaseItem, PurchasePayment
│   ├── payroll/                 # Employee + Quincenas + CS + recibos PDF
│   ├── task_master/             # Mix, Task con componentes recursivos
│   ├── budgets/                 # Budget versionado + BudgetItem con snapshot + PDF
│   ├── budget_analysis/         # Cruce Presupuesto vs Real
│   ├── treasury/                # TreasuryEntry + signals
│   ├── tracking/                # Snapshots + TaskExecution + VarianceAnalyzer
│   └── imports/                 # 9 importadores CSV/XLSX
├── mamsys/                      # Config: settings (base/dev/prod), urls, urls_public, celery
├── templates/                   # Base + partials reutilizables (sidebar filtrado por permisos)
├── docs/
│   ├── SPEC.md                  # Especificación funcional (fuente de verdad — 12 secciones)
│   └── STATUS.md                # Este documento
├── requirements/                # base.txt, dev.txt, prod.txt
├── docker-compose.yml           # Postgres 16 + Redis 7 (no se usa en local con brew)
├── manage.py
├── pyproject.toml               # ruff, pytest, coverage
└── README.md
```

---

## 4. Apps en detalle

### 4.1 `apps.core` — abstracciones

- `TimestampedModel`: `created_at`, `updated_at`, `created_by`, `updated_by`. Toda app de negocio hereda.
- `CatalogItem`: name + code + active + order. Base para todos los catálogos.
- `AuditLog`: registro de cambios con JSON diff (placeholder).
- **`apps/core/pdf.py`**: helper `render_pdf(request, template, context, filename)` con WeasyPrint. Renderiza el template y devuelve `HttpResponse` con `Content-Disposition: attachment`. Usado por Budget PDF y Talonarios.

### 4.2 `apps.accounts` — usuarios

- `User` custom (`AbstractBaseUser + PermissionsMixin`), `email` = `USERNAME_FIELD`.
- `is_staff` solo para super-admin del SaaS, no para admins de org.
- Templates de allauth sobrescritos con estilo Mamsys.

### 4.3 `apps.organizations` — tenancy

- `Organization(TenantMixin)`: `auto_create_schema=True`. Cada save crea un schema Postgres.
- `Domain(DomainMixin)`: host → tenant.
- `Membership`: user ↔ org con `role` (FK Protect) + `is_active`.
- `Invitation`: token UUID + expiración.
- **Signal `provision_default_roles`**: al crear Org, carga los 5 roles base (Admin, Área Técnica, Tesorería, RRHH, Solo Lectura).
- **`services.signup_organization()`** (atómico): User + Org + Domain + EmailAddress allauth (verificada) + Membership Admin. **Importante**: si no creás EmailAddress, allauth no deja loguear.

### 4.4 `apps.permissions` — autorización

- `Role`: per-org, `permissions` es `JSONField(default=list)` con strings de `constants.py`.
- `ObjectAccess`: GenericForeignKey + `can_view` / `can_edit`.
- **`constants.py`**: 36 permission codes en grupos: VIEW/EDIT/MANAGE por dominio.
  - Obras: `view_projects`, `edit_projects`, `manage_projects`
  - Compras: `view_purchases`, `edit_purchases`, `edit_purchase_items`, `delete_purchases`, `view_admin_purchases`, `edit_admin_purchases`, `register_payments`
  - Nómina: `view_payroll`, `edit_payroll`, `close_payroll`, `pay_payroll`, `view_employees`, `edit_employees`, `view_sensitive_employee_data`, `manage_social_charges`
  - Maestros: `view_task_master`, `edit_task_master`, `approve_task_suggestions`
  - Presupuestos: `view_budgets`, `edit_budgets`, `approve_budgets`
  - Tracking: `view_tracking`
  - Tesorería: `view_treasury`, `edit_treasury`, `reconcile_treasury`
  - Pricing: `view_pricing`, `edit_pricing`
  - Reportes: `view_reports`, `export_reports`
  - Admin org: `manage_users`, `manage_roles`, `manage_catalog`, `manage_organization`
- **5 roles base** provistos automáticamente al crear Org (en `services.py`):
  - **Admin** — todos los permisos
  - **Área Técnica** — obras, presupuestos, maestros, tracking, pricing read
  - **Tesorería** — compras, tesorería, pagos
  - **RRHH** — empleados, nómina, cargas sociales
  - **Solo Lectura** — view_* de todo
- **`checks.user_has_permission(user, org, code)`**: superuser → True; sino mira el Membership activo del user en esa org.
- **`decorators.py`** (creado en sesión 2026-05-15):
  - `get_current_org(request)` — extrae tenant; en `public` schema devuelve None (no aplica gating).
  - `@require_permission(code)` — para FBVs.
  - `PermissionRequiredMixin` — para CBVs. Define `required_permission = "code"`.
- **`templatetags/permissions_tags.py`**: `{% has_perm "code" as can_x %}` para sidebar/templates.
- **Aplicado actualmente a list views de**: procurement, payroll (3 views), projects, tracking, task_master (2 views), budgets, budget_analysis, pricing, treasury, imports (todas: index/upload/confirm/log).
- **Falta** (pendiente):
  - UI de CRUD de Role (hoy solo se edita por admin Django).
  - UI de asignación de Role en Membership (idem).
  - Gating en views de detail/edit (hoy solo lists). Para muchos casos basta porque list es la puerta de entrada.

### 4.5 `apps.currencies` (SHARED)

- `Currency`: code (ISO), name, symbol, active.
- Data migration siembra ARS/USD/EUR.

### 4.6 `apps.catalog` — 14 modelos via factory

| Modelo | Notas clave |
|---|---|
| `Rubro` | name único |
| `Subrubro` | FK Rubro PROTECT; (rubro, name) único |
| `Unit` | symbol único, category (length/area/volume/weight/time/global) |
| `BusinessComponent` | clasificador transversal (TERRENO, VENTA UF) |
| `ProjectStatus` | Solo Terreno, En Construcción, Completada |
| `EmployeeStatus` | Activo/Suspendido/Renuncio/Despedido |
| `Position` | Ayudante/Medio Of./Oficial/RT |
| `Bank` | Galicia, Ciudad, etc. |
| `BankAccount` | bank + company + currency + account_number + cbu + alias |
| `Team` | name + leader (FK Employee opcional) |
| `Supplier` | code, category, M2M Rubros, contacto, CUIT |
| `Material` | rubro, subrubro opcional, unit, last_known_price |
| `Subcontract` | unit, typical_supplier opcional |
| `ExtraordinaryConcept` | name + type (income/expense), (type,name) único |
| `TrackingCategory` | name + color hex |

**Factory en `apps/catalog/views.py`**: dict `CATALOGS` mapea slug → `{"model": ..., "form": ..., "label": ..., ...}`. Agregar un nuevo catálogo = 1 entrada + 1 ModelForm. Genera list/create/update/URLs automáticamente.

### 4.7 `apps.companies`

- Per-tenant. Una org tiene N sociedades (PASFAS SA, 350 SRL).
- Campos: name, legal_name, tax_id (CUIT), iva_condition, iibb_number, fiscal_address.
- **Wizard**: cuando un user entra al tenant y no hay ninguna Company, lo redirige al alta. En `apps/companies/middleware.py` o similar.

### 4.8 `apps.projects` — Obras

- Per-tenant. FK PROTECT a Company + opcional a ProjectStatus.
- `name` (+ unique por company), `code` (unique parcial), address, fechas, `project_manager` (FK User), notes, `is_archived`.
- UI: list con filtro archivadas, detail con tabs (Resumen / Compras / MO / Presupuestos / Seguimiento — último activo, resto placeholder).

### 4.9 `apps.pricing`

- `ExchangeRateType`: name único, currency_from→currency_to, is_default, `calculation_type` (`manual` | `weighted_combination`), `combination_formula` JSON (ej.: `{"BNA": 0.7, "CCL": 0.3}`).
- `ExchangeRate`: rate_type + date (unique) + rate Decimal(15,4) + source (manual/imported/calculated).
- `Price` polimórfico: `GenericForeignKey` apunta a Material/Subcontract/Position/Mix/Task. amount, currency, effective_date, supplier opcional, source, `is_reference` flag, `source_purchase_item_id` para idempotencia con signal de compras.

**Servicios**:
- `CurrencyConversionService.get_rate(rate_type, date)`: busca exacta → más cercana anterior (ventana 30 días) → `ExchangeRateNotFoundError`. Para tipos calculados (70/30): resuelve recursivo y persiste el resultado como ExchangeRate `source=calculated` (cache idempotente).
- `CurrencyConversionService.convert(amount, from, to, date, rate_type)`: maneja inversión cuando el tipo está en dirección opuesta.
- `PriceLookupService.get_current_price(item, currency, date, rate_type, strategy)`:
  - `most_recent` (default): el Price más reciente con `is_reference=True`.
  - `weighted_average_n_days`: promedio ponderado por recencia.
  - `min_n_days`: mínimo de la ventana.

UI: `/cotizaciones/` lista tipos con última tasa y default, detail con histórico 60 días + form rápido día.

### 4.10 `apps.procurement`

- `Purchase`: cabecera con `purchase_type` (obra/admin/cadeteria), `document_type` (FA/FB/FC/presupuesto/remito/ticket/otro), document_number, invoice_date, `is_subcontract`, `is_itemized` (auto), supplier+email, company, project (obligatorio si type=obra), rubro/subrubro/business_component, montos en moneda original (sin IVA, IVA 21/10.5, IIBB, total), original_currency, `exchange_rate_used` + cache totales ARS/USD oficial/USD CCL, payment_method, week_to_pay, due_date, status (draft/to_pay/paid_partial/paid/cancelled), warehouse (placeholder), notes.
- `PurchaseItem`: FK Purchase CASCADE, item_description, **XOR(material, subcontract)** validado en clean(), quantity, unit, unit_price, total (auto-calc), subrubro override, tracking_category, task_id placeholder.
- `PurchasePayment`: payment_date, amount, currency, exchange_rate_used opcional, payment_method, reference.

**Signals**:
- `PurchaseItem post_save` (compra confirmada): upsert `Price` con `source_purchase_item_id` ancla idempotente. Actualiza `Material.last_known_price` / `Subcontract.last_known_price`.
- `Purchase post_save` (transición confirmada): alimenta Prices para items existentes.
- `PurchasePayment post_save/delete`: recalcula `Purchase.status` según suma pagos.

UI: list con 8 filtros + 4 KPIs, bandeja "A pagar" por week_to_pay, cuenta corriente por proveedor.

### 4.11 `apps.payroll` — 4 turnos

| Modelo | Función |
|---|---|
| `Employee` | datos laborales: company, status, position, teams M2M, boss self-FK, primary_rubro, hire/termination_date, arca_registered |
| `EmployeePersonalData` (1-1) | nombre, doc, CUIL, nacimiento, estado civil, contacto |
| `EmployeeBanking` (1-1) | bank, cbu, cvu_mercado_libre |
| `EmergencyContact` (1-N) | full_name, relationship, phone |
| `PayrollPeriod` | quincena por sociedad: period_number, month, year, fechas, días/horas, plus generales (overtime%, presentismo%), status |
| `PositionPlus` | adicional por puesto/quincena |
| `PayrollEntry` | empleado-en-quincena con snapshots, value_jornal, asistencia, horas, subtotales, neto redondeado, banco/efectivo, billetes 7 denominaciones |
| `PayrollAllocation` | imputación a N obras con pct (suma=100), jornal/net/CS amounts, social_charges_status (estimated/real) |
| `PayrollExtraordinary` | bonos/adelantos con FK ExtraordinaryConcept |
| `SocialChargesPayment` | pago CS por sociedad/mes |

**Cálculo (`PayrollEntry.recalculate`)** — SPEC §9.2:
```
attendance_subtotal = days_worked × value_jornal
position_plus_total = (PositionPlus del puesto) × días
overtime_amount = horas_extra × (jornal/hours_weekday) × (1 + plus_overtime_pct/100)
extraordinary_subtotal = suma firmada (income - expense)
gross = attendance + position_plus + overtime - vacations - late_hours_amount
presentismo = gross × plus_presentismo_pct/100
net = round10(gross + presentismo + extraordinary)
cash = net - bank (no-negative)
billetes = greedy con [1000, 500, 200, 100, 50, 20, 10]
```

**Servicios**:
- `pre_generate_entries_for_period(period)`: stub para cada empleado activo. Idempotente.
- `SocialChargesProrateService.prorate(payment)`: distribuye CS proporcional al bruto del mes → pct allocation. Marca `social_charges_status='real'`. Idempotente.

**Signals**: cambios en `PayrollExtraordinary` / `PayrollAllocation` re-guardan la entry → dispara `recalculate()`.

UI: list quincenas + detail con tabla empleados + edit entry con extras + allocations + billetes editables. **Talonarios PDF**: `period_talonarios_pdf` view en `apps/payroll/views.py:288` renderiza `payroll/pdf/talonarios.html` (un recibo operativo por página por empleado).

### 4.12 `apps.task_master`

- `Mix`: receta de mezcla con name único, output_unit, version, active.
- `MixComponent`: XOR(material, sub_mix) + quantity_per_unit + input_unit. clean() detecta ciclos.
- `Task`: tarea maestra con code jerárquico opcional, rubro, subrubro, output_unit, version.
- `TaskComponent`: 5 source_types (material/labor/subcontract/sub_mix/sub_task). Exactamente un FK lleno. Auto-clasifica materials o labor.
- `TaskAdjustmentSuggestion`: lo llena tracking en Fase 7.

**Detección de ciclos** (`validators.py`): DFS antes de guardar componentes con sub_mix/sub_task.

**`TaskCostCalculator.calculate(task_or_mix, currency, date, rate_type)`**:
- Material/subcontract → `PriceLookupService` con fallback a `last_known_price`.
- Labor (Position) → último `value_jornal` de PayrollEntry de empleados ese puesto.
- sub_mix/sub_task → recurse.
- Devuelve `CostBreakdown` con materials/labor + componentes + sub_breakdowns navegables.

UI: `/maestros/` landing → tareas + mezclas. Editor inline con costo en vivo. Sub-mezclas como `<details>` colapsables anidados.

**Inline formsets**: `MixComponentFormSet` y `TaskComponentFormSet` requieren `fk_name="mix"` y `fk_name="task"` respectivamente (la FK ambigua porque puede apuntar a sub_mix/sub_task).

### 4.13 `apps.budgets`

- `Budget`: project, name, version, status (draft/submitted/approved/rejected/superseded), snapshot al cerrar (pricing_date, exchange_rate_type, exchange_rate_value), totales, approved_by/at.
- `BudgetItem`: FK Task + quantity + snapshot unit_cost/total_cost/breakdown + `recipe_snapshot` JSON.

**Servicios**:
- `BudgetCalculatorService.compute()`: draft usa `TaskCostCalculator` (vivo); cerrados leen snapshot.
- `BudgetSnapshotService.freeze()`: por cada item llama TaskCostCalculator, persiste unit_cost + breakdown + recipe_snapshot.
- `BudgetApprovalService.submit() / approve() / reject() / clone_as_new_version()`.

UI: `/presupuestos/` con filtros, alta con inline formset, detail con KPIs + acciones contextuales + banner 🔒 cuando is_locked. **PDF**: `budget_pdf` view en `apps/budgets/views.py:187` renderiza `budgets/pdf/budget.html`.

### 4.14 `apps.budget_analysis`

- `BudgetVsActualReport`: persiste cruce con totales + data JSON.

**`BudgetActualCrossService.compute(budget, cutoff_date, currency, rate_type)`**:
- Planned: snapshot del Budget.
- Actual:
  - Compras hasta cutoff excluyendo canceladas. Por compra con ítems, prorratea total c/IVA según subtotal items. `is_subcontract` → subcontracts; sino materials. Group by rubro/task.
  - Nómina: `PayrollAllocation` cuyo `payroll_period.end_date ≤ cutoff`. Suma `net_amount + social_charges_amount` → bucket labor.
- Conversión multi-moneda automática.

UI: `/presupuesto-vs-real/` con form (budget + cutoff + moneda + rate_type + checkbox guardar). Breakdown por categoría/rubro/tarea con varianzas coloreadas.

### 4.15 `apps.treasury`

- `TreasuryEntry`: entry_type (income/expense/transfer/currency_exchange), category (10 valores), date, company, bank_account (null → efectivo), counterpart_account, amount + currency, multi-moneda con exchange_rate_used + counterpart_amount/currency, project opcional, 3 OneToOne a sources (purchase_payment, social_charges_payment, payroll_period), is_reconciled + reconciled_at/by.

**Signals automáticas**:
- `PurchasePayment` → upsert TreasuryEntry expense/supplier_payment.
- `SocialChargesPayment` → upsert TreasuryEntry expense/social_charges_payment.

**`compute_account_balances(cutoff_date, company_id)`**: saldo = ingresos − egresos por bank_account.

UI: `/tesoreria/` con 8 filtros + KPIs + toggle conciliación inline. `/tesoreria/saldos/` balance por cuenta.

### 4.16 `apps.tracking`

- `ProjectExecutionSnapshot`: foto por fecha con totals (materials/labor/subcontracts/CS real+estimado). Unique (project, snapshot_date).
- `TaskExecution`: planned vs actual (acumulado de PurchaseItems con task_id + PayrollAllocations con task_id), variance properties.
- `ProjectForecast`: placeholder.

**`TrackingService.snapshot_project(project, date)`**: agrega compras + nómina, persiste snapshot idempotente, llama `update_task_executions()` que cruza con el último Budget approved.

**`VarianceAnalyzer.scan(threshold_pct, min_samples)`**: agrupa TaskExecutions por task; si ≥N obras con varianza promedio > umbral, crea/actualiza `TaskAdjustmentSuggestion PENDING`.

**`approve_suggestion()` / `reject_suggestion()`**: aprobar incrementa `Task.version`.

UI: `/seguimiento/obras/<pk>/` snapshot + tabla TaskExecutions. `/seguimiento/sugerencias/` con escaneo + acciones.

### 4.17 `apps.imports` — 9 importadores

`ImportLog` persiste cada importación. `BaseImporter` parsea CSV/XLSX, valida required columns, llama hook `process_row(row, dry_run)`. Captura `ValueError` como error de fila. Filas con error NO se persisten.

| Slug | Modelo | Notas |
|---|---|---|
| `rubro` | Rubro | trivial |
| `subrubro` | Subrubro | match Rubro por nombre |
| `material` | Material | match Rubro + Subrubro + Unit |
| `supplier` | Supplier | M2M rubros por nombre |
| `employee` | Employee | crea PersonalData + Banking en cascada |
| `exchange_rate` | ExchangeRate | match RateType por nombre |
| `purchase` | Purchase + items | **groupby document_number** — header con N filas, primera fila = cabecera, resto = items. Wraps `_process_group` en `transaction.atomic()` para rollback de items si una fila falla. |
| `unit` | Unit | category obligatoria |
| `payroll_period` | PayrollPeriod | quincenas históricas con totales sumarios (no cargas detalle de empleados) |

UI: `/importadores/` grilla → upload (dry-run preview) → confirm. Cada import deja `ImportLog` con errores por fila JSON.

Encoding/separador autodetect (UTF-8/Latin-1, coma/punto-y-coma).

---

## 5. Flujos end-to-end (probados)

### Compra de obra
```
Crear Purchase → status=to_pay
  ↓
PurchaseItem.save() → signal sync_price_from_item
    → upsert pricing.Price (idempotente por source_purchase_item_id)
    → Material.last_known_price actualizado
  ↓
PurchasePayment.save() → signal create_entry_for_purchase_payment
    → treasury.TreasuryEntry upsert
    → Purchase.status recalculado (paid_partial / paid)
```

### Quincena con CS
```
PayrollPeriod.save() → pre_generate_entries_for_period
  ↓
Por Employee activo: PayrollEntry stub (jornal último, días totales)
  ↓
Usuario edita entry → recalculate() en cascada
  → lee extras firmados, calcula attendance/overtime/presentismo/gross/net
  → distribuye gross/net a Allocations según pct
  → billetes desde cash_amount
  ↓
Tesorería carga SocialChargesPayment
  → Signal SocialChargesProrateService.prorate:
    - pct_employee = entry.gross / total_gross_mes
    - asigna CS a cada Allocation según pct
    - marca social_charges_status='real'
  → Signal create_entry_for_social_charges → TreasuryEntry
```

### Presupuesto vs Real
```
Budget(draft) con BudgetItems → costos en vivo via TaskCostCalculator
  ↓
submit() o approve() → BudgetSnapshotService.freeze()
  → congela pricing_date, exchange_rate_value
  → por item: unit_cost + breakdown + recipe_snapshot
  ↓
[tiempo: cargan Compras + Quincenas]
  ↓
BudgetActualCrossService.compute():
  - Planned ← snapshot
  - Actual ← Compras + Allocations hasta cutoff
  - Group by categoria/rubro/task
  - Conversión multi-moneda
```

---

## 6. Tests — 215 pasando

| App | Tests |
|---|---|
| accounts | 3 |
| organizations | 4 |
| permissions | 13 (4 constants + 9 decorators/template tag) |
| catalog | 9 |
| companies | 3 |
| projects | 5 |
| currencies | 1 |
| pricing | 23 |
| procurement | 19 |
| payroll | 46 |
| task_master | 15 |
| budgets | 7 |
| budget_analysis | 7 |
| treasury | 6 |
| tracking | 10 |
| imports | 29 (3 nuevos importers cada uno con 4-6 tests) |
| **TOTAL** | **215** |

Comando: `.venv/bin/pytest -q` (~7 min en M1).

---

## 7. Gotchas / fixes que ya pegaron (no repetir)

1. **Python 3.11 oficial tira SSL error con allauth en Mac**. Usar `brew install python@3.12`.
2. **`django-rules` no existe en PyPI**, es `rules` (sin prefijo). En `requirements/base.txt`.
3. **`timezone` shadow en Organization**: el modelo tiene field `timezone`, no usar `from django.utils import timezone`. Import `tz_now` así: `from django.utils.timezone import now as tz_now`.
4. **Multi-backend login**: con `rules` instalado, allauth no sabe qué backend usar al loguear post-signup. En `services.signup_organization` especificar `login(request, user, backend="allauth.account.auth_backends.AuthenticationBackend")`.
5. **debug_toolbar URLs faltan**: incluir condicional en `mamsys/urls.py` Y `mamsys/urls_public.py` (django-tenants usa rutas distintas según schema).
6. **EmailAddress allauth ausente**: si creás User a mano (no por allauth), `signup_organization` debe crear `EmailAddress(verified=True, primary=True)` o el login falla con "Email no verificado".
7. **Inline formset FK ambigua**: `MixComponentFormSet` y `TaskComponentFormSet` requieren `fk_name="mix"` / `fk_name="task"` porque el modelo tiene N FKs al mismo target (sub_mix/sub_task).
8. **`transaction.on_commit` no firing en tests**: si un signal envuelve la creación en `on_commit`, los tests con `@pytest.mark.django_db` no lo disparan a menos que sea `transactional=True`. Para payroll signals removimos el wrapper.
9. **PurchaseImporter atomic rollback**: cada grupo (document_number) debe envolverse en `transaction.atomic()` para que si una fila de items falla, el header y los items anteriores se reviertan. Está en `_process_group`.
10. **`today|date:"H:i"` con `localdate()`**: `localdate()` devuelve `date`, no `datetime`. Si el template quiere mostrar hora, usar `tz_now()` (datetime) o sacar `H:i` del format spec. Pasaba en algún PDF.
11. **Test flaky `test_variance_analyzer_requires_min_samples`**: depende de orden de ejecución. No bloqueante. Pendiente fix.
12. **`PermissionRequiredMixin` y `self.request`**: si en tests instanciás la view a mano y llamás `dispatch(request)` sin pasar por `setup()`, `self.request` no existe. El mixin actual usa el `request` del argumento de `dispatch`, no `self.request` (fix del 2026-05-15).
13. **migrate vs migrate_schemas**: con django-tenants, `migrate` no toca los schemas de tenants. Siempre `migrate_schemas --shared` (corre en public Y en todos los tenants). Para uno solo: `migrate_schemas --schema=<slug>`.

---

## 8. Decisiones del SPEC §11 (asumidas como default)

13 supuestos que el código respeta; aún no firmados explícitamente:

1. ✓ N obras por quincena (no limitado a 2)
2. ✓ Suma jornales = bruto con tolerancia
3. ✓ Conteo billetes automático con override
4. ✓ Moneda sueldos ARS por default
5. ⏳ No emitir recibos legales (solo operativos)
6. ✓ Compras alimentan precios automáticamente
7. ✓ Más reciente con `is_reference=True` como default PriceLookup
8. ✓ Subcontract separado de Material
9. ✓ Subcontrato por compra entera, no por ítem
10. ✓ Cálculo 70/30 automático
11. ✓ "Nocito" como tipo custom de cotización
12. ✓ Cotización ausente → anterior más cercana en 30 días
13. ✓ Asistencia con días/faltas/justificadas/vacaciones/late/overtime

---

## 9. Lo que falta

### Pulido funcional (en curso)

| Pieza | Esfuerzo | Valor |
|---|---|---|
| UI CRUD de Role + asignación a Membership | medio | alto |
| Dashboard real con KPIs por rol (hoy placeholder) | medio | medio |
| PDF Listado por banco (transferencias del mes) | bajo | medio |
| Cuenta corriente proveedor multi-moneda | bajo | medio |
| Saldos tesorería con conversión a moneda elegida | bajo | medio |
| Más importadores: Cotizaciones (CSV con N tasas), BankAccount, Catálogos restantes | bajo | medio |

### Pulido técnico

| Pieza | Esfuerzo | Valor |
|---|---|---|
| Tailwind compilado (sacar CDN, npm + tailwindcss CLI) | bajo | alto |
| Vendoreado HTMX/Alpine | bajo | alto |
| Static files con WhiteNoise + compression | bajo | medio |
| Tests de views (hoy solo unit + servicios + decorators) | medio | medio |
| Onboarding wizard al crear org (preseed catálogos mínimos) | medio | medio |
| Fix flaky `test_variance_analyzer_requires_min_samples` | bajo | bajo |
| Gating fino: aplicar permisos en views de edit/detail (hoy solo list) | medio | medio |

### Faltantes SPEC

- Conversión `task_id` int placeholder → FK real a `task_master.Task` en `PurchaseItem` y `PayrollAllocation`.
- UI para editar receta de Task **al aprobar sugerencia** (hoy solo bumpea version).
- Forecasting real en `ProjectForecast`.
- Exportación a Excel de reportes (Cash Flow, Base MO) — servicios existen, faltan endpoints.
- Templates HTML separados para impresión (vs WeasyPrint).

### Infra / deploy (todo pendiente)

- Pipeline CI (GitHub Actions con pytest).
- Dockerfile + docker-compose prod.
- Backup automático schema por tenant.
- Secrets manager.
- Rate limiting + logs estructurados.
- Sentry.
- Healthcheck endpoint.

### Comercial (pendiente)

- Billing (plan por org, Stripe/MercadoPago).
- Trial period.
- Marketing site (hoy landing minimalista).

---

## 10. Cómo retomar con Claude en la nueva máquina

Cuando arranque Claude Code en la otra Mac:

1. **Auto-memory**: este proyecto ya tiene memorias en `~/.claude/projects/-Users-ripio-Documents-saas/memory/`. En la otra Mac, esa ruta cambia según el path del directorio. Si querés portar las memorias, copialas a `~/.claude/projects/<nueva-ruta-codificada>/memory/`. O dejá que Claude reconstruya leyendo este STATUS.md + `docs/SPEC.md` desde cero.

2. **Primer prompt sugerido** en la nueva sesión:
   > "Levanté Mamsys en una compu nueva. Leé `docs/STATUS.md` y `docs/SPEC.md` para tomar contexto. Estoy en la fase de pulido post-SPEC: ya están las 11 fases del roadmap, 215 tests, 9 importadores, 2 PDFs, permisos finos aplicados a list views. Sigamos por [X]."

3. **Estado al cierre 2026-05-15** (último commit `492961c`):
   - Sesión actual quedó iniciando UI de gestión de roles (CRUD de Role + asignación a Membership). Se hizo el plan + se revisó modelo `Role` y `Membership`, pero no se escribió código nuevo.
   - Si retomás eso: views CRUD viven mejor en `apps/organizations/` (porque Role es SHARED y la asignación va por Membership). URLs: `/admin-org/roles/`, `/admin-org/usuarios/`. Form con checkboxes agrupados por scope (usar las constantes de `apps/permissions/constants.py`). Permisos requeridos: `manage_roles` y `manage_users`.

4. **Comandos útiles**:
   ```bash
   # Estado git
   git log --oneline -10
   git status

   # Re-verificar tests
   .venv/bin/pytest -q

   # Re-crear el tenant demo si hace falta
   .venv/bin/python manage.py shell  # ver sección 1.6

   # Re-poblar catálogos mínimos en demo (si lo borrás y rearmás)
   # NO hay management command para eso todavía — se hace por UI o admin.
   ```

5. **Si algo del SPEC requiere decisión**: leer la sección 11 de `docs/SPEC.md` (13 supuestos default) y la sección "Decisiones SPEC §11" arriba.

---

## 11. Credenciales y secretos

> **Importante**: estos son secretos LOCALES de desarrollo. Para producción, todo va a secrets manager.

- **Tenant demo (local)**:
  - URL: http://demo.localhost:8000/
  - Email: `mateo@demo.com`
  - Pass: `ContraseñaLarga123`
  - Es admin del tenant Demo (Membership con Role "Admin").

- **Superuser de plataforma**: el que crees con `createsuperuser`. Usuario sugerido: `mateo.monsegur@ripio.com`.

- **DB local**: usuario `mamsys`, sin password, trust auth.

- **GitHub PAT compartido en chat** (un token con prefix `ghp_`): **revocar y crear uno nuevo** en https://github.com/settings/tokens. Mejor configurar SSH key: https://github.com/settings/keys

---

## 12. Spec de referencia

La fuente de verdad funcional está en [`docs/SPEC.md`](SPEC.md) — 12 secciones, ~20 semanas de roadmap.

Estructura del SPEC:
1. Visión y alcance
2. Glosario
3. Roles y permisos
4. Modelo conceptual (entidades)
5. Catálogos
6. Multi-moneda y cotizaciones
7. Compras (KPS)
8. Maestros (Tareas/Mezclas)
9. Nómina (MO) — incluye cálculos detallados
10. Roadmap por fases (11 fases — todas completas)
11. Decisiones default (13 supuestos)
12. Notas de implementación

---

*Última actualización: 2026-05-15. Commit ref: `492961c`. Tests: 215/215.*
