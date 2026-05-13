# Mamsys V.1 — Especificación funcional y técnica

> Documento fuente de verdad del proyecto. Sujeto a revisión y ajuste durante el desarrollo.

## Índice

1. [Contexto general y objetivo](#1-contexto-general-y-objetivo)
2. [Stack técnico](#2-stack-técnico)
3. [Arquitectura de apps Django](#3-arquitectura-de-apps-django)
4. [Modelo de multi-tenancy y permisos](#4-modelo-de-multi-tenancy-y-permisos)
5. [Modelos de datos por app](#5-modelos-de-datos-por-app)
6. [Flujos críticos del negocio](#6-flujos-críticos-del-negocio)
7. [UX por rol y por sección](#7-ux-por-rol-y-por-sección)
8. [Reportes y exportaciones](#8-reportes-y-exportaciones)
9. [Reglas de cálculo](#9-reglas-de-cálculo)
10. [Roadmap de implementación](#10-roadmap-de-implementación)
11. [Decisiones por defecto a confirmar](#11-decisiones-por-defecto-a-confirmar)
12. [Estilo, diseño y convenciones](#12-estilo-diseño-y-convenciones)

---

## 1. Contexto general y objetivo

### Qué se construye

Un sistema SaaS multi-tenant para constructoras pyme argentinas que reemplaza un ecosistema actual de planillas de Google Sheets. El sistema gestiona:

- Compras (KPS) y nómina de empleados (MO) como datos base
- Seguimiento de obras con análisis de varianzas
- Maestro de tareas y mezclas con recetas jerárquicas
- Presupuestos versionados con snapshot de precios
- Cruce presupuesto vs real por obra
- Tesorería con ingresos, egresos, transferencias, cambio de monedas
- Multi-moneda (ARS, USD) con múltiples cotizaciones configurables (BNA, CCL, etc.)

### Modelo de negocio

- SaaS multi-tenant: una sola instancia, múltiples empresas (organizaciones).
- Cada organización tiene varias sociedades (S.A., S.R.L., etc.) y varios usuarios con roles diferenciados.
- Vendible a otras pymes constructoras.

### Principios de diseño

- Las planillas de Sheets son la inspiración, no la prescripción. Donde Sheets duplica datos, el sistema usa fuentes de verdad únicas y reportes derivados.
- Los maestros se nutren automáticamente del transaccional. Las compras alimentan precios; las quincenas alimentan costos de obra.
- Multi-moneda nativo. Toda valuación puede convertirse al vuelo entre monedas con la cotización configurada.
- Snapshots en cierres. Presupuestos aprobados, quincenas cerradas y cotizaciones del día se congelan; cambios posteriores no afectan registros históricos.
- Permisos finos. No solo por sección, también por obra y por sociedad.
- Auditoría completa. Todo cambio se registra con quién, cuándo y qué.

---

## 2. Stack técnico

| Capa | Herramienta |
|------|-------------|
| Lenguaje | Python 3.12+ |
| Framework | Django 5.x |
| API | Django REST Framework |
| Base de datos | PostgreSQL 16+ |
| Frontend | HTMX + Alpine.js + Tailwind CSS |
| Auth | django-allauth (no usar el admin de Django como UI de usuarios finales) |
| Multi-tenant | django-tenants (schema por organización) |
| Permisos por objeto | django-rules |
| Tareas asíncronas | Celery + Redis (para generación de reportes pesados, recálculos masivos) |
| Generación PDF | WeasyPrint (recibos, presupuestos, talonarios) |
| Excel | openpyxl (importar / exportar planillas) |
| Tests | pytest + pytest-django + factory-boy |
| CI/CD | A definir (GitHub Actions / GitLab CI) |
| Deploy | A definir (Docker + cualquier PaaS o VPS) |

**Decisión clave de multi-tenancy:** se usa django-tenants con schema separado por organización. Razones:

- Aislamiento fuerte de datos sensibles (tesorería, nóminas).
- Migraciones por tenant simples.
- Si una org necesita backup/export individual, es directo.
- Si una org crece mucho, se puede mover su schema a una DB dedicada sin tocar el código.

---

## 3. Arquitectura de apps Django

Se organizan en 4 grupos lógicos:

### Apps base transversales

| App | Responsabilidad |
|-----|-----------------|
| core | Modelos abstractos (TimestampedModel, OrganizationOwnedModel, CatalogItem), mixins, utilidades, signals genéricas. |
| accounts | Custom User, login, registro, verificación email, password reset, perfil. |
| organizations | Organizaciones (tenants), Sociedades (Companies) dentro de cada org, Memberships User↔Org, Invitaciones. |
| permissions | Roles configurables, permisos por sección, permisos por objeto (obra, sociedad), helpers/decoradores. |
| catalog | Todos los índices maestros: Rubros, Subrubros, Componentes, Posiciones, Equipos, Unidades, Monedas, Tipos de Cotización, Bancos, Cuentas Bancarias, Proveedores, Depósitos, Estados, Conceptos Extraordinarios, Subcontratos. |

### Apps de datos transaccionales (Capa 1)

| App | Responsabilidad |
|-----|-----------------|
| projects | Obras (Projects). Estado, sociedad, fechas, equipo asignado, manager. |
| procurement | Compras (Purchases) con cabecera + items opcionales. Pagos. Facturas administrativas. |
| payroll | Empleados, Quincenas (PayrollPeriod), Entradas de Quincena (PayrollEntry), Imputaciones a Obras (PayrollAllocation), Extraordinarios, Plus por Puesto, Carga Social. |

### Apps de análisis y maestros (Capa 2-3)

| App | Responsabilidad |
|-----|-----------------|
| pricing | Histórico de precios (auto-poblado por compras + manual), cotizaciones de monedas, conversiones. |
| task_master | Maestro de Tareas, Maestro de Mezclas (modelos separados pero análogos), componentes recursivos, sugerencias de ajuste desde tracking. |
| tracking | Seguimiento de obras: agregaciones por obra/rubro/tarea, comparaciones, previsiones. |

### Apps de planificación y control (Capa 4)

| App | Responsabilidad |
|-----|-----------------|
| budgets | Presupuestos versionados (P1, P2, P3) con snapshot de receta y precio, Maestro de Presupuestos. |
| budget_analysis | Cruce presupuesto vs real, varianzas, reportes guardados. |
| treasury | Movimientos financieros (ingresos, egresos, transferencias, cambios de moneda), agregados de compras y nómina. |
| reporting | Dashboards, exportaciones a Excel/PDF, reportes guardados, talonarios. |

---

## 4. Modelo de multi-tenancy y permisos

### Tenancy

- Cada Organization tiene su propio schema en PostgreSQL (via django-tenants).
- El schema `public` contiene: Organizations, Users (con email único global), Memberships, datos del SaaS (planes, billing).
- El resto de los modelos viven en el schema de cada tenant.

### Custom User

- Modelo `User` con email como `USERNAME_FIELD` (no username).
- `is_staff` se reserva para super-admins de la plataforma (vos como dueño del SaaS).
- Los "admins" de una organización NO tienen `is_staff=True`. Su poder lo da su rol en Membership.

### Membership

- Relación User ↔ Organization con `role` (FK a Role).
- Un usuario puede pertenecer a varias organizaciones (un consultor que asesora a varias empresas).
- Al hacer login se le pide elegir organización si tiene varias activas.

### Roles base (creados al provisionar una org)

| Rol | Descripción |
|-----|-------------|
| Admin | Acceso total a la organización. Gestiona usuarios, catálogos, configuración. |
| Área Técnica / Gestión | Carga compras, abre facturas en ítems, edita maestros, ve seguimiento. |
| Tesorería | Carga pagos, gestiona movimientos financieros, ve facturas en solo-lectura. Edita facturas administrativas propias. |
| RRHH / Nómina | Carga quincenas, gestiona empleados, paga sueldos. |
| Solo Lectura | Ve dashboards y reportes pero no edita. |

Cada rol es editable y duplicable por la organización. Pueden crear roles custom.

### Permisos del sistema

Constantes en `permissions/constants.py`. Lista no exhaustiva:

- `VIEW_PROJECTS` / `EDIT_PROJECTS` / `MANAGE_PROJECTS`
- `VIEW_PURCHASES` / `EDIT_PURCHASES` / `EDIT_PURCHASE_ITEMS` / `DELETE_PURCHASES`
- `VIEW_ADMIN_PURCHASES` / `EDIT_ADMIN_PURCHASES`
- `REGISTER_PAYMENTS`
- `VIEW_PAYROLL` / `EDIT_PAYROLL` / `CLOSE_PAYROLL` / `PAY_PAYROLL`
- `VIEW_EMPLOYEES` / `EDIT_EMPLOYEES` / `VIEW_SENSITIVE_EMPLOYEE_DATA` (CBU, DNI)
- `VIEW_TASK_MASTER` / `EDIT_TASK_MASTER` / `APPROVE_TASK_SUGGESTIONS`
- `VIEW_BUDGETS` / `EDIT_BUDGETS` / `APPROVE_BUDGETS`
- `VIEW_TRACKING`
- `VIEW_TREASURY` / `EDIT_TREASURY` / `RECONCILE_TREASURY`
- `VIEW_PRICING` / `EDIT_PRICING`
- `VIEW_REPORTS` / `EXPORT_REPORTS`
- `MANAGE_USERS` / `MANAGE_ROLES`
- `MANAGE_CATALOG`
- `MANAGE_ORGANIZATION`
- `MANAGE_SOCIAL_CHARGES`

### Permisos por objeto

Además del rol global, hay permisos por:

- **Proyecto/Obra:** un usuario puede tener acceso solo a obras específicas.
- **Sociedad:** un usuario puede ver solo datos de sociedades específicas.

Implementado con django-rules y un modelo `ObjectAccess`:

```
ObjectAccess
- user (FK)
- content_type + object_id (genérico)
- can_view (bool)
- can_edit (bool)
```

Helper en todas las views/querysets:

```python
def get_accessible_projects(user):
    """Devuelve queryset de Projects que el user puede ver."""
```

---

## 5. Modelos de datos por app

> Nota: se describen los modelos en lenguaje natural. La implementación concreta (Django ORM, migraciones, índices) la decide Claude Code respetando las convenciones de cada app.

### 5.1 core

**TimestampedModel (abstracto)**
- `created_at` (auto)
- `updated_at` (auto)
- `created_by` (FK User, nullable, SET_NULL)
- `updated_by` (FK User, nullable, SET_NULL)

**OrganizationOwnedModel (abstracto, hereda de TimestampedModel)**
- `organization` (FK Organization, CASCADE)

> Nota multi-tenant: con django-tenants el campo `organization` puede ser redundante (cada schema ya está aislado), pero se mantiene para queries cross-tenant en el schema `public` (reportes administrativos del SaaS).

**CatalogItem (abstracto, hereda de OrganizationOwnedModel)**
- `name` (CharField)
- `code` (CharField, opcional)
- `active` (BooleanField, default True)
- `order` (PositiveInteger, default 0)
- Meta: ordering por order, name.

**AuditLog**
- Registro automático de cambios significativos.
- Generado por signals en modelos críticos (Purchase, PayrollEntry, Budget, TreasuryEntry, Task, Mix).
- Campos: `user`, `timestamp`, `action` (create/update/delete/approve), `content_type`, `object_id`, `changes` (JSONField con diff).

### 5.2 accounts

**User (custom AbstractBaseUser)**
- `email` (unique, USERNAME_FIELD)
- `first_name`, `last_name`
- `phone`
- `is_active`, `is_staff`, `email_verified`
- `created_at`
- Manager custom con `create_user` y `create_superuser`.

**EmailVerificationToken**
- `user`, `token` (UUID), `expires_at`, `used_at`.

**PasswordResetToken**
- Análogo al anterior.

**UX**
- Páginas HTML propias para: registro, login, recuperar contraseña, verificar email, editar perfil.
- Nunca usar `/admin/` como UI para usuarios finales.
- El admin de Django solo lo usa el super-admin del SaaS.

### 5.3 organizations

**Organization (vive en schema public)**
- `name`, `slug` (unique), `legal_name`, `tax_id` (CUIT)
- `country` (default 'AR'), `timezone` (default 'America/Argentina/Buenos_Aires')
- `plan` (FK a Plan en billing, opcional)
- `is_active`
- Hereda de `TenantMixin` de django-tenants.

**Domain (django-tenants)**
- Modelo standard de django-tenants.

**Membership (vive en schema public)**
- `user`, `organization`, `role` (FK a Role)
- `is_active`, `invited_by`, `accepted_at`
- `unique_together`: (user, organization)

**Invitation**
- `organization`, `email`, `role`, `token`, `invited_by`, `expires_at`, `accepted_at`.

**Company (Sociedad — vive en schema del tenant)**
- `name`, `legal_name`, `tax_id` (CUIT)
- `iva_condition` (Responsable Inscripto, Monotributo, Exento)
- `iibb_number` (opcional)
- `fiscal_address`
- `active`

> Una `Organization` (cliente del SaaS) tiene N `Company` (sus razones sociales: PASFAS SA, 350 SRL, GESTION, MONOTRIBUTO, ÑADEMAETE SA, etc.).

### 5.4 catalog

Todos los catálogos heredan de `CatalogItem` salvo indicación.

**Rubro**
- Plano. Ejemplos: TRABAJOS PRELIMINARES, DEMOLICION, ESTRUCTURA, ALBAÑILERIA, INSTALACIONES, TERMINACIONES, etc.

**Subrubro**
- `rubro` (FK Rubro, PROTECT)
- Jerarquía estricta: un Subrubro pertenece a un único Rubro.

**BusinessComponent**
- Componentes transversales que clasifican operaciones (compras, ventas, ingresos, egresos).
- Ejemplos: TERRENO, VENTA UF, etc.
- No está atado a Subrubro: cualquier compra puede combinar cualquier Componente con cualquier Subrubro.

**Position (Puesto)**
- Tipos de mano de obra: Ayudante, Medio Oficial, Oficial, Líder Equipo, Segundo, Oficial Especializado, Administrativo, Representante Técnico, Otro, Pintor.

**Team (Equipo)**
- `name` (ej: "Equipo Adan", "Equipo Naty")
- `leader` (FK Employee, opcional — el RT/líder)
- `notes`

**Unit (Unidad de medida)**
- `symbol` (m², m³, kg, hs, JORNAL, GL, UNI, ML, etc.)
- `category` (longitud, peso, volumen, tiempo, global, etc.)

**Currency (vive en schema public)**
- `code` (ARS, USD, EUR), `name`, `symbol`.

**ExchangeRateType (Tipo de Cotización)**
- `name` (BNA, CCL, Nocito, 70/30, etc.)
- `currency_from` (FK Currency)
- `currency_to` (FK Currency)
- `is_default` (bool — cuál usa el sistema si no se especifica)
- `calculation_type`: manual / weighted_combination
- `combination_formula` (JSONField, opcional): para tipos calculados, ej: `{"BNA": 0.7, "CCL": 0.3}`

**Supplier (Proveedor)**
- `code` (CharField — ej: "CRN" + número)
- `category` (CharField — ARIDOS, CORRALON, etc.)
- `rubros` (M2M con Rubro — un proveedor vende en varios rubros)
- `contact_name` (Asistente)
- `email`, `phone`, `address`
- `tax_id` (CUIT)
- `notes`

**Warehouse (Depósito)**
- `address`
- `keeper_employee` (FK Employee, opcional — quién es el responsable/retira)
- `keeper_name` (CharField — si no es un empleado del sistema)

**Bank**
- Catálogo de bancos: Galicia, Ciudad, Provincia, etc.

**BankAccount (Cuenta Bancaria)**
- `bank` (FK Bank)
- `company` (FK Company — qué sociedad es titular)
- `currency` (FK Currency)
- `account_number`, `cbu`, `alias`

**EmployeeStatus**
- Estados: Activo, Suspendido, Renuncio, Despedido.

**ProjectStatus**
- Estados: Solo Terreno, En Construcción, Completada (configurable; cada empresa puede agregar).

**ExtraordinaryConcept**
- `name`
- `type`: income / expense
- Ingresos: Redondeo, Guardias, Aguinaldo, Diferencia, Otros, Premio, Vacaciones, Préstamo, BONO, Retroactivo.
- Egresos: Adelanto, Compra Merc, Cuota Alimentaria, Liquidación, Multas, Otros, Préstamos, OSDE.

**Material**
- `rubro`, `subrubro` (FK opcional)
- `unit` (FK Unit — unidad de compra)
- `description`
- `last_known_price` (cache — calculado de la compra más reciente)

**Subcontract (Subcontrato — catálogo)**
- `name` (ej: "Estudio de Suelo", "Cálculo Estructural")
- `description`
- `unit` (FK Unit — típicamente GL, M2, ML)
- `typical_supplier` (FK Supplier, opcional)

**TrackingCategory (sub-planillas configurables)**
- `color` (hex)
- Configurables por empresa, sin set fijo.

### 5.5 projects

**Project (Obra)**
- `name`, `code`
- `company` (FK Company, PROTECT — qué sociedad es titular)
- `address`
- `start_date`, `estimated_end_date`, `actual_end_date`
- `status` (FK ProjectStatus)
- `project_manager` (FK User, opcional)
- `notes`
- `is_archived`

### 5.6 pricing

**ExchangeRate**
- `rate_type` (FK ExchangeRateType)
- `date`
- `rate` (DecimalField, 15,4)
- `source`: manual / imported / calculated
- `unique_together`: (rate_type, date)
- Index: (rate_type, -date)

**Price**
- Polimórfico con GenericForeignKey: `item` puede ser Material, Position, Subcontract, Mix, Task.
- `amount` (DecimalField, 15,4)
- `currency` (FK Currency)
- `effective_date` (Date)
- `supplier` (FK Supplier, opcional — referencia histórica)
- `source`: purchase / manual / import
- `source_purchase_item` (FK PurchaseItem, opcional)
- `is_reference` (BooleanField, default True) — False para precios de oferta o circunstanciales que no se usan en cálculos
- `notes`
- Index: (content_type, object_id, -effective_date)

**Servicio CurrencyConversionService**

Métodos:
- `convert(amount, from_currency, to_currency, date, rate_type=None) -> Decimal`
- `get_rate(rate_type, date, fallback_to_previous=True) -> ExchangeRate`
- `get_price_at(item, date, in_currency='ARS', rate_type=None) -> Decimal`

Reglas:
- Si existe cotización en `date`, usarla.
- Si no, buscar la más cercana anterior (default).
- Si tampoco hay, lanzar `ExchangeRateNotFoundError` con sugerencia.
- Para tipos calculados (70/30), resolver recursivamente las dependencias.

**Servicio PriceLookupService**
- `get_current_price(item, currency='ARS', date=None, rate_type=None) -> Decimal`
- Estrategia configurable por org en `OrganizationSettings`:
  - `most_recent` (default): el Price más reciente con `is_reference=True`
  - `weighted_average_n_days`: promedio ponderado de últimos N días
  - `min_n_days`: mínimo de últimos N días

### 5.7 procurement

**Purchase (Compra / Factura)**

Identificación y clasificación:
- `purchase_type`: obra / admin / cadeteria
- `document_type`: factura_a / factura_b / factura_c / presupuesto / remito / ticket / otro
- `document_number` (Nº PPTO/FC)
- `invoice_date`
- `is_subcontract` (bool — toda la compra es un subcontrato)
- `is_itemized` (bool — flag automático, True cuando tiene al menos un PurchaseItem)

Proveedor y sociedad:
- `supplier` (FK Supplier, PROTECT)
- `supplier_email` (override del mail del catálogo)
- `company` (FK Company, PROTECT — Sociedad)

Imputación principal (cabecera):
- `project` (FK Project, PROTECT) — obligatorio si `purchase_type='obra'`
- `rubro` (FK Rubro, PROTECT)
- `subrubro` (FK Subrubro, PROTECT, opcional)
- `business_component` (FK BusinessComponent, PROTECT, opcional)
- `detail` (descripción libre, ej: "REPLANTEO Y VERIFICACION DE MEDIDAS")
- `main_item_description` (opcional — cuando no se abre por ítems)

Montos en moneda original:
- `original_currency` (FK Currency)
- `amount_without_tax` (MONTO SIN IVA)
- `iva_21`, `iva_10_5` (DecimalField)
- `perc_iibb` (Percepción IIBB)
- `total_amount` (MONTO TOTAL)

Conversión:
- `exchange_rate_used` (FK ExchangeRate, opcional)
- `total_in_ars`, `total_in_usd_oficial`, `total_in_usd_ccl` (DecimalFields cacheados)

Pago:
- `payment_method` (texto libre o catálogo, opcional)
- `week_to_pay` (CharField)
- `due_date` (DateField)
- `status`: draft / to_pay / paid_partial / paid / cancelled

Logística:
- `warehouse` (FK Warehouse, opcional)

Meta:
- `notes` (Observaciones)

**PurchasePayment (Pago de una compra)**
- `purchase` (FK Purchase)
- `payment_date`
- `amount`
- `currency` (FK Currency)
- `exchange_rate_used` (FK ExchangeRate, opcional)
- `bank_account` (FK BankAccount, opcional)
- `payment_method`
- `reference` (Nº transferencia, cheque, etc.)
- `notes`

Lógica: la suma de `PurchasePayment.amount` (convertidos a moneda de la compra) determina si la Purchase está `paid_partial` o `paid`.

**PurchaseItem**
- `purchase` (FK Purchase, CASCADE)
- `item_description` (override descriptivo, opcional)
- Uno de los dos según `is_subcontract` de la compra:
  - `material` (FK Material, PROTECT) — si NO es subcontrato
  - `subcontract` (FK Subcontract, PROTECT) — si ES subcontrato
- `quantity`, `unit` (FK Unit), `unit_price` (en moneda original), `total`
- Sub-imputación opcional:
  - `subrubro` (FK Subrubro, opcional — puede ser distinto al de la cabecera para detalle)
  - `tracking_category` (FK TrackingCategory, opcional)
  - `task` (FK Task, opcional — qué tarea del maestro se está ejecutando)
- `notes`

Signal: al crear/actualizar un PurchaseItem:
- Si `purchase.status ≠ draft`, crear un registro `Price` con el `unit_price` (source=purchase, effective_date=invoice_date, currency=original_currency, item=material o subcontract).
- Actualizar `Material.last_known_price` (o `Subcontract.last_known_price`).
- Setear `purchase.is_itemized = True`.

**Permisos clave de compras**
- Las compras de obra (`purchase_type='obra'`) son propiedad de Gestión/Área Técnica. Tesorería las ve en solo-lectura excepto para registrar pagos.
- Las compras administrativas (`purchase_type='admin'` o cadeteria) son propiedad de Tesorería. Gestión no las ve o las ve solo en lectura.
- Cualquier compra puede abrirse en ítems, decisión de Gestión. Tesorería puede pagar sin necesidad de que esté abierta.
- Si Tesorería necesita modificar la cabecera de una factura de obra → pide a Gestión.

**Jerarquía estricta de imputación**

```
Project (Obra)
  └── Rubro
       └── Subrubro (FK estricta a Rubro)
            └── (Component es transversal, no está bajo Subrubro)
            └── PurchaseItem.material → del catálogo Material
```

### 5.8 payroll

**Employee (Empleado)**

Datos laborales:
- `internal_id` (CharField — ID interno)
- `status` (FK EmployeeStatus — Activo/Suspendido/Renuncio/Despedido)
- `company` (FK Company — sociedad que le paga)
- `position` (FK Position — Puesto)
- `teams` (M2M Team — puede estar en varios)
- `boss` (FK Employee a sí mismo, opcional — Jefe de Obra)
- `primary_rubro` (FK Rubro, opcional — solo informativo / hint)
- `hire_date`
- `termination_date` (opcional)
- `arca_registered` (BooleanField — alta en ARCA/AFIP)

Datos personales (un-a-uno con `EmployeePersonalData`, separado para permisos finos):
- `first_name`, `last_name`, `full_name` (auto)
- `nationality`
- `document_type` (DNI/PAS), `document_number`
- `cuil`
- `birth_date`, `age` (calculado)
- `marital_status`
- `children_count`

Contacto:
- `phone_landline`, `phone_mobile`
- `email`
- `address`

Contacto de emergencia (modelo separado `EmergencyContact`, 1:N):
- `full_name`, `relationship`, `phone`

Datos bancarios (un-a-uno con `EmployeeBanking`):
- `bank` (FK Bank)
- `cbu`
- `cvu_mercado_libre` (CVU billetera virtual)

Cache:
- `last_known_salary` (DecimalField — del último Valor Jornal cobrado)
- `last_known_currency` (FK Currency)

> Nota importante: el sueldo base NO vive en Employee. Se define en cada quincena (`PayrollEntry.value_jornal`). El campo `last_known_salary` es solo cache para mostrar referencias.

**PayrollPeriod (Quincena)**

Identificación:
- `period_number` (1 o 2 del mes)
- `month`, `year`
- `start_date`, `end_date`
- `company` (FK Company — quincena por sociedad)
- `talonario_name` (ej: "1era Quincena de Diciembre")

Configuración de días:
- `working_days` (días laborales L-V, ej: 10)
- `saturdays` (ej: 2)
- `holidays` (ej: 1)
- `total_days` (calculado o configurado, ej: 13)

Configuración de horas:
- `hours_weekday` (horas L-V, ej: 8)
- `hours_saturday` (ej: 7)
- `total_hours` (ej: 94)

Plus generales:
- `plus_overtime_pct` (Plus H. Extra, ej: 12%)
- `plus_presentismo_pct` (Plus Presentismo, ej: 2.30%)

Status:
- open / closed / paid

Snapshot: al cerrar, se congelan todos los datos y no se permiten más cambios (salvo reapertura por Admin).

**PositionPlus (Plus por puesto y quincena)**
- `payroll_period` (FK PayrollPeriod)
- `position` (FK Position)
- `amount` (DecimalField — ej: $18 para Ayudante, $22 para Medio Oficial, $25 para Oficial)
- `currency` (FK Currency)

**PayrollEntry (Empleado en quincena)**

Identificación:
- `payroll_period` (FK PayrollPeriod)
- `employee` (FK Employee)
- `unique_together`: (payroll_period, employee)

Snapshot del empleado al momento (para auditoría):
- `team_snapshot`, `boss_snapshot`, `company_snapshot`, `position_snapshot`, `primary_rubro_snapshot`
- `suspended` (BooleanField — sin importar el estado general del empleado, en esta quincena específica)

Sueldo base:
- `value_jornal` (Valor Jornal del empleado en esta quincena)
- `currency` (FK Currency)

Asistencia:
- `days_worked` (días efectivos trabajados)
- `attendance_amount` (= `days_worked × value_jornal`, calculado)

Ausencias:
- `absences` (Faltas, cantidad)
- `justified_absences` (Justificadas)
- `vacations` (Vacaciones, días)
- `vacations_amount` (DecimalField)
- `vacations_detail` (texto)

Horas:
- `late_hours` (H. Tarde, cantidad)
- `late_hours_amount` (DecimalField, descuento)
- `late_hours_detail` (texto)
- `overtime_hours` (H. Extra, cantidad)
- `overtime_amount` (calculado: `overtime_hours × valor_hora × (1 + plus_overtime_pct)`)

Subtotales (calculados):
- `gross` (Bruto)
- `attendance_subtotal` ($ Asistencia)
- `hours_subtotal` ($ Horas)
- `extraordinary_subtotal` ($ Extraordinarios)
- `presentismo_subtotal` ($ Presentismo)

Pago:
- `net` (Neto, redondeado a múltiplo de 10)
- `bank_amount` ($ Banco)
- `cash_amount` ($ Efectivo)

Billetes (calculados automáticamente desde `cash_amount`, editables):
- `bills_1000`, `bills_500`, `bills_200`, `bills_100`, `bills_50`, `bills_20`, `bills_10` (PositiveIntegers)
- Servicio `BillCalculator` que minimiza cantidad de billetes.

Comentarios:
- `receipt_observations` (figura en el recibo)
- `internal_notes`

Cache convertidos:
- `gross_in_ars`, `net_in_ars`, `gross_in_usd_oficial`, `net_in_usd_oficial`, etc.

**PayrollAllocation (Imputación a Obra)**
- `payroll_entry` (FK PayrollEntry, CASCADE)
- `project` (FK Project, PROTECT)
- `subrubro` (FK Subrubro, opcional)
- `tracking_category` (FK TrackingCategory, opcional)
- `task` (FK Task, opcional — a qué tarea específica imputó horas)
- `pct` (DecimalField — % de la jornada del empleado en esta obra, 0-100)
- `jornal_amount` (DecimalField — el monto del jornal imputado a esta obra)
- `net_amount` (DecimalField — neto prorrateado)
- `social_charges_amount` (DecimalField — CS imputado, llenado por servicio cuando Tesorería carga el pago)
- `total_amount` (= `net_amount + social_charges_amount`, calculado)
- `social_charges_status`: estimated / real (estimado mientras no haya pago de CS real)

> Validación: la suma de `pct` de todas las allocations de un PayrollEntry debe ser 100 (con tolerancia).
> Validación: la suma de `jornal_amount` debe igualar el bruto laboral (con tolerancia de centavos).
>
> El sistema soporta N obras por quincena, no limitado a 2.

**PayrollExtraordinary (Ingreso/Egreso Extraordinario)**
- `payroll_entry` (FK PayrollEntry, CASCADE)
- `concept` (FK ExtraordinaryConcept)
- `amount` (DecimalField)
- `quantity` (DecimalField, opcional — ej: cantidad de días de Presentismo)
- `notes`

**SocialChargesPayment (Pago de Carga Social)**
- `company` (FK Company)
- `period_month`, `period_year` (o vinculado a PayrollPeriod)
- `total_amount`
- `currency` (FK Currency)
- `payment_date`
- `reference` (Nº comprobante)
- `created_by` (Usuario de Tesorería)
- `notes`

**Servicio SocialChargesProrateService**

Cuando se carga un SocialChargesPayment:

1. Toma todos los `PayrollEntry` de empleados de esa Company en ese mes (ambas quincenas).
2. Calcula el bruto total de la sociedad en el mes.
3. Para cada `PayrollEntry`, calcula su % de participación = `gross / total_gross`.
4. El CS que le toca al empleado = `payment.total_amount × pct_participation`.
5. Para cada `PayrollAllocation` del empleado, le asigna CS proporcional a su `pct` de obra.
6. Setea `social_charges_status='real'` en todas las allocations afectadas.

Estado estimado (mientras no hay pago real):
- Cada org configura un % histórico de referencia (ej: 40% del bruto).
- Las allocations muestran CS estimado con un visual de "estimación pendiente de pago real".

### 5.9 task_master

**Mix (Mezcla)**
- `name` (ej: "CONCRETO CON HIDROFUGO")
- `code` (opcional)
- `output_unit` (FK Unit — UM, ej: M2, M3)
- `description`
- `active`
- `version` (PositiveInteger — incrementa con cambios aprobados)

**MixComponent**
- `mix` (FK Mix, CASCADE)
- Uno de los dos:
  - `material` (FK Material)
  - `sub_mix` (FK Mix — recursión)
- `quantity_per_unit` (Cant. UA — cuánto se consume por unidad del Mix padre)
- `input_unit` (FK Unit — UA)
- `notes`

Validación: prevenir ciclos en sub_mix.

**Task (Tarea Maestra)**
- `code` (jerárquico opcional: A.1.5, A.1.6, etc. — auto-generable o manual)
- `name` (ej: "CERCO DE OBRA EN CHAPA")
- `rubro` (FK Rubro)
- `subrubro` (FK Subrubro, opcional)
- `output_unit` (FK Unit — UT, Unidad de Tarea)
- `description` (Detalle)
- `active`
- `version` (PositiveInteger)

**TaskComponent**
- `task` (FK Task, CASCADE)
- `source_type` (los 5 tipos):
  - `material` → FK material lleno
  - `labor` → FK position lleno
  - `subcontract` → FK subcontract lleno
  - `sub_mix` → FK sub_mix lleno
  - `sub_task` → FK sub_task lleno
- `classification`: materials / labor (calculado pero almacenado para reportes rápidos)
- `quantity_per_unit` (Cant. UA)
- `input_unit` (FK Unit — UA)
- `detail` (descripción específica del componente)
- `notes`

Validación: exactamente uno de los 5 FK debe estar lleno, coherente con `source_type`.
Validación: prevenir ciclos recursivos en sub_task/sub_mix.

**TaskAdjustmentSuggestion**

Sugerencia automática generada por tracking cuando detecta varianzas sistemáticas.
- `task` (FK Task)
- `component` (FK TaskComponent)
- `current_quantity` (la que dice el maestro)
- `suggested_quantity` (la observada en obras reales)
- `based_on_projects` (M2M Project — obras analizadas)
- `sample_size` (cuántas ejecuciones se analizaron)
- `variance_pct` (porcentaje de desvío)
- `status`: pending / approved / rejected
- `reviewed_by` (FK User)
- `reviewed_at`
- `notes`

Flujo aprobado (opción A): al aprobar una sugerencia, se incrementa la `version` del Task y se actualiza el TaskComponent. Los presupuestos existentes mantienen su snapshot, los nuevos usan la versión actualizada.

**Servicio TaskCostCalculator**

Métodos:
- `calculate_cost(task_or_mix, date, currency, rate_type) -> CostBreakdown`
- Resuelve recursivamente sub-mixes y sub-tasks.
- Para cada material/subcontract: usa `PriceLookupService` con la estrategia configurada por la org.
- Para cada labor (Position): usa el último Valor Jornal de esa posición (calculado del promedio o del Plus + Valor base — TBD por configuración org).
- Devuelve estructura `CostBreakdown`:

```
total_cost
total_in_ars
total_in_usd
components: [
  {type, item, quantity, unit_cost, total, currency_original},
  ...
]
```

### 5.10 tracking

**ProjectExecutionSnapshot**

Foto del estado de una obra a una fecha. Se regenera por job programado (Celery) o al vuelo.
- `project` (FK Project)
- `snapshot_date`
- `total_materials_cost` (DecimalField — en ARS y USD)
- `total_labor_internal_cost`
- `total_labor_subcontract_cost`
- `total_social_charges_cost` (estimado + real)
- `breakdown` (JSONField — desglose por rubro/subrubro/task)

**TaskExecution**

Ejecución real de una tarea del maestro en una obra. Permite el cruce contra presupuesto.
- `project` (FK Project)
- `task` (FK Task)
- `task_version` (qué versión del maestro se usó al planificar)
- `planned_quantity` (del presupuesto)
- `actual_quantity` (acumulado de PurchaseItems + PayrollAllocations imputados a esta task)
- `planned_cost` / `actual_cost` (en ARS y USD)
- `completion_pct`
- `status`: not_started / in_progress / completed

**ProjectForecast (Previsión / CS)**
- `project` (FK Project)
- `forecast_date`
- `forecasted_total_cost`
- `forecasted_completion_date`
- `forecasted_social_charges`
- `notes`

**Servicio VarianceAnalyzer**
- Detecta tareas donde el consumo real difiere sistemáticamente del planificado.
- Genera `TaskAdjustmentSuggestion` para revisión.

### 5.11 budgets

**Budget (Presupuesto)**
- `project` (FK Project)
- `name`
- `version` (PositiveInteger — Presupuesto 1, 2, 3)
- `status`: draft / submitted / approved / rejected / superseded

Snapshot al cerrarse (status submitted o approved):
- `pricing_date` (DateField — fecha de los precios usados)
- `exchange_rate_type` (FK ExchangeRateType — qué cotización se usó)
- `exchange_rate_value` (DecimalField — la cotización congelada)

Totales (snapshot):
- `total_in_ars`
- `total_in_usd`
- `materials_cost`, `labor_cost`, `subcontracts_cost` (breakdown)
- `margin_pct` (markup)
- `total_with_margin`

Aprobación:
- `approved_by` (FK User)
- `approved_at`
- `notes`

**BudgetItem**
- `budget` (FK Budget)
- `task` (FK Task)
- `task_version` (versión del Maestro congelada)
- `quantity`
- `unit_cost` (snapshot calculado en el momento de cerrar)
- `total_cost`
- Desglose snapshot:
  - `materials_cost`
  - `labor_cost`
  - `subcontracts_cost`
- `recipe_snapshot` (JSONField — copia completa de la receta del Task en ese momento)
- `order` (PositiveInteger)

> Por qué snapshot: un presupuesto aprobado se mantiene estable. Si después cambia el precio del cemento o la receta de Colocación de Pisos, el presupuesto aprobado NO cambia. Para ver "qué pasaría con los nuevos precios" se crea un nuevo Budget (P2, P3).

**BudgetMaster (Maestro de Presupuestos)**

Es un índice/listado, no un modelo separado. Una pantalla que muestra todos los presupuestos de la organización con filtros: obra, sociedad, estado, fecha, rango de montos.

### 5.12 budget_analysis

**BudgetVsActualReport**
- `project` (FK Project)
- `budget` (FK Budget — qué presupuesto se compara)
- `cutoff_date`
- `in_currency` (FK Currency — moneda del análisis)
- `rate_type` (FK ExchangeRateType)
- `total_planned`
- `total_actual`
- `variance_amount`
- `variance_pct`
- `data` (JSONField — detalle por task/rubro/subrubro)
- `generated_by` (FK User)
- `generated_at`

**Servicio BudgetActualCrossService**
- Toma un Budget aprobado.
- Para cada BudgetItem (Task), busca todos los `PurchaseItem.task = X` y `PayrollAllocation.task = X` del Project.
- Suma reales por componente (materiales, MO interna, subcontratos, CS).
- Compara con el snapshot del BudgetItem.
- Devuelve breakdown navegable: Total → Rubro → Subrubro → Task → Componentes.

### 5.13 treasury

**TreasuryEntry (Movimiento Financiero)**
- `entry_type`: income / expense / transfer / currency_exchange
- `date`
- `company` (FK Company)
- `bank_account` (FK BankAccount — cuenta principal del movimiento)
- `counterpart_account` (FK BankAccount, opcional — para transferencias y cambios)
- `amount`
- `currency` (FK Currency)
- `exchange_rate_used` (FK ExchangeRate, opcional)
- `counterpart_amount` (DecimalField, opcional — para currency_exchange: cuánto se recibió en la otra moneda)
- `counterpart_currency` (FK Currency, opcional)
- `project` (FK Project, opcional — si el movimiento se asocia a una obra)
- `category`:
  - `supplier_payment`
  - `payroll_payment`
  - `social_charges_payment`
  - `taxes`
  - `financing`
  - `admin`
  - `client_payment` / `client_advance`
  - `other`
- Origen automático (signals):
  - `source_purchase` (FK Purchase, opcional)
  - `source_payroll_period` (FK PayrollPeriod, opcional)
  - `source_social_charges_payment` (FK SocialChargesPayment, opcional)
- `description`, `notes`
- `is_reconciled` (bool)
- `reconciled_at`, `reconciled_by`

**Signals automáticas**
- Al confirmar una `PurchasePayment`: crea TreasuryEntry de tipo `expense`, categoría `supplier_payment`, vinculada.
- Al pagar una `PayrollPeriod`: crea múltiples TreasuryEntry (uno por banco y uno por efectivo).
- Al confirmar un `SocialChargesPayment`: crea TreasuryEntry.
- Tesorería puede crear TreasuryEntry manualmente para movimientos que no tienen origen en compras/nómina (ingresos de clientes, financiamiento, impuestos administrativos).

**Vistas clave de Tesorería**
- Cash Flow por fecha, sociedad, cuenta, moneda.
- Saldos por cuenta (calculados de movimientos).
- Conciliación bancaria (importar extracto y marcar movimientos).
- % de Banco mensual por sociedad (porcentaje de pagos por banco vs efectivo).

---

## 6. Flujos críticos del negocio

### 6.1 Carga de compra (KPS)

**Flujo de Gestión:**
1. Crear Compra (status=draft).
2. Cargar cabecera: proveedor, sociedad, obra, rubro, subrubro, componente, totales con IVA.
3. (Opcional) Abrir en ítems: cargar materiales con cantidades y precios unitarios. La suma de ítems debe cuadrar con el subtotal neto.
4. Confirmar (status=to_pay). La compra queda visible para Tesorería.
5. Al confirmarse, si tiene ítems, cada ítem crea un Price.

**Flujo de Tesorería (después):**
1. Ve la compra en su bandeja "A pagar".
2. Registra pagos parciales o totales con PurchasePayment.
3. Si el pago acumulado = total → purchase.status = paid. Si parcial → paid_partial.
4. Cada pago genera un TreasuryEntry.

**Flujo de actualización ítems (Gestión, post-pago):**
- Gestión puede seguir editando ítems incluso después del pago, sin que cambie el total para Tesorería.
- Si hay diferencia entre suma de ítems y cabecera → warning visible.

### 6.2 Carga de quincena

1. Admin/RRHH crea PayrollPeriod (sociedad, fechas, días, plus generales).
2. Configura PositionPlus para cada puesto vigente.
3. Sistema pre-genera PayrollEntry por cada empleado activo de la sociedad (con snapshot de equipo/jefe/posición).
4. Para cada empleado:
   - Carga Valor Jornal.
   - Carga asistencia (días, faltas, justificadas, vacaciones).
   - Carga horas (tarde, extra).
   - Carga extraordinarios (Ingreso/Egreso del catálogo).
   - Configura imputación a obras (PayrollAllocation) — porcentaje y subrubro.
5. Sistema calcula automáticamente bruto, subtotales, neto.
6. Sistema calcula automáticamente conteo de billetes para `cash_amount`.
7. Admin revisa, ajusta lo que necesite, cierra la quincena (status=closed).
8. RRHH paga (status=paid). Se generan TreasuryEntry automáticamente.
9. Tesorería carga el pago de Carga Social cuando corresponde → CS se prorratea a las allocations.

### 6.3 Aprobación de sugerencias del Maestro de Tareas

1. Job de Celery analiza periódicamente PurchaseItem y PayrollAllocation vs receta esperada de cada Task.
2. Si detecta varianza sistemática (umbral configurable por org, ej: 10% en 5 ejecuciones), crea TaskAdjustmentSuggestion pendiente.
3. Área Técnica recibe notificación → revisa, aprueba/rechaza.
4. Al aprobar: `Task.version += 1`, `TaskComponent.quantity_per_unit` se actualiza.
5. Presupuestos existentes mantienen su snapshot. Los nuevos usan la versión actual.

### 6.4 Creación de presupuesto

1. Crear Budget para una obra (status=draft).
2. Agregar BudgetItem (cada uno es una Task con cantidad).
3. Sistema calcula `unit_cost` al vuelo según precios actuales y cotización seleccionada.
4. Al cerrar (submitted o approved): snapshot completo — receta congelada, precios congelados, cotización congelada.
5. Presupuestos se versionan: cuando hay un P2, el P1 pasa a `superseded` pero se conserva.

### 6.5 Cruce presupuesto vs real

1. Usuario elige Budget aprobado + cutoff_date + moneda + rate_type.
2. Servicio agrega todo lo real ejecutado para ese Project:
   - Sumar PurchaseItems donde `task ∈ tasks del budget`.
   - Sumar PayrollAllocations donde `task ∈ tasks del budget`.
   - Imputar CS proporcional.
3. Comparar contra el snapshot del Budget.
4. Mostrar tabla navegable por Rubro → Subrubro → Task → Componentes.
5. Guardar como BudgetVsActualReport (opcional, para historial).

---

## 7. UX por rol y por sección

### Sidebar de navegación

```
- Dashboard
- Obras
  - Lista
  - Seguimiento (selección de obra → tracking)
- Compras
  - De obra
  - Administrativas (solo Tesorería)
  - A pagar (solo Tesorería)
- Nómina
  - Empleados
  - Quincenas
  - Carga Social (solo Tesorería/Admin)
- Maestros
  - Tareas
  - Mezclas
  - Sugerencias pendientes
- Presupuestos
  - Lista
  - Cruce vs Real
- Tesorería
  - Movimientos
  - Cuentas y saldos
  - Conciliación
  - Cash Flow
- Catálogos
  - Rubros / Subrubros / Componentes
  - Proveedores
  - Materiales
  - Subcontratos
  - Puestos / Equipos
  - Sociedades
  - Bancos / Cuentas
  - Depósitos
  - Cotizaciones
  - Conceptos Extraordinarios
- Reportes
- Configuración
  - Usuarios y roles (solo Admin)
  - Mi organización (solo Admin)
  - Mi perfil
```

Las secciones se filtran según permisos del rol del usuario.

### Pantallas tipo

- Lista con filtros (siempre con barra superior de filtros, búsqueda y exportar).
- Detalle con tabs cuando hay subsecciones (ej: una obra tiene tabs Resumen / Compras / MO / Presupuestos / Seguimiento).
- Formularios con HTMX para validaciones incrementales y campos dependientes (ej: al elegir Rubro se filtran Subrubros).
- Tablas editables inline para carga masiva de quincenas (estilo planilla).
- Modales para acciones puntuales (registrar pago, aprobar sugerencia).

---

## 8. Reportes y exportaciones

### Reportes que el sistema genera

- **Base MO** (rejunte de quincenas para tracking) — exportable a Excel con las columnas exactas que se muestran en la planilla actual.
- **Resumen de Quincena** por equipo y por sociedad — pantalla + PDF.
- **Talonarios** (recibos operativos por empleado, agrupados por equipo) — PDF.
- **Listado de billetes** total de una quincena — PDF.
- **Listado por banco** (para transferencias) — PDF y CSV.
- **Presupuesto completo** — PDF y Excel.
- **Cruce Presupuesto vs Real** — pantalla + PDF + Excel.
- **Cash Flow** — pantalla + Excel.
- **Cuenta corriente proveedor** — pantalla + PDF.
- **KPIs por obra** — pantalla.

### Importaciones

Para migrar datos de Sheets:
- Importador de Catálogos (Rubros, Subrubros, Materiales, Proveedores, Empleados, Sociedades, etc.) — CSV/Excel.
- Importador de Compras históricas — CSV/Excel con mapeo de columnas guardable.
- Importador de Quincenas históricas — CSV/Excel.
- Importador de Maestro de Tareas y Mezclas — CSV/Excel.
- Importador de Cotizaciones — CSV/Excel.

Cada importador debe:
- Permitir mapear columnas del archivo a campos del modelo.
- Validar antes de guardar (preview con errores resaltados).
- Permitir aceptar fila por fila o todo de una.
- Guardar log de importación con resumen de éxitos/errores.

---

## 9. Reglas de cálculo

### 9.1 Conversión de monedas

Servicio `CurrencyConversionService`:

```
convert(amount, from_currency, to_currency, date, rate_type='default'):
    if from_currency == to_currency: return amount
    rate = get_rate(rate_type, date)
    # rate.currency_from == USD, rate.currency_to == ARS típicamente
    if from_currency == 'USD' and to_currency == 'ARS': return amount * rate
    if from_currency == 'ARS' and to_currency == 'USD': return amount / rate
    # Para cruces no-USD: convertir vía USD
```

Si falta cotización: usar la más cercana anterior dentro de 30 días. Si no hay → exception con sugerencia.

### 9.2 Cálculo de Quincena

```
attendance_subtotal = days_worked * value_jornal
overtime_amount = overtime_hours * (value_jornal / hours_per_day) * (1 + plus_overtime_pct / 100)
extraordinary_subtotal = sum(income_extraordinaries) - sum(expense_extraordinaries)

gross = attendance_subtotal
      + overtime_amount
      + (position_plus.amount * days_worked if applicable)
      - vacations_amount
      - late_hours_amount

presentismo_subtotal = gross * plus_presentismo_pct / 100 (si aplica)

net = gross + presentismo_subtotal + extraordinary_subtotal
net_rounded = round_to_nearest_10(net)
```

> Nota: los detalles exactos dependen de la práctica de cada org. Se implementa configurable via `OrganizationPayrollSettings` para que cada empresa ajuste su fórmula sin tocar el código.

### 9.3 Cálculo de costo de Task / Mix

Servicio recursivo:

```
calculate_cost(task, date, currency, rate_type):
    total = 0
    for component in task.components:
        if component.source_type == 'material':
            price = price_lookup.get_current_price(component.material, currency, date, rate_type)
        elif component.source_type == 'subcontract':
            price = price_lookup.get_current_price(component.subcontract, currency, date, rate_type)
        elif component.source_type == 'labor':
            price = get_labor_cost(component.position, currency, date)
        elif component.source_type == 'sub_mix':
            price = calculate_cost(component.sub_mix, date, currency, rate_type)
        elif component.source_type == 'sub_task':
            price = calculate_cost(component.sub_task, date, currency, rate_type)

        total += component.quantity_per_unit * price
    return total
```

### 9.4 Prorrateo de Carga Social

```
on_social_charges_payment_created(payment):
    entries = PayrollEntry.objects.filter(
        payroll_period__company=payment.company,
        payroll_period__year=payment.period_year,
        payroll_period__month=payment.period_month
    )
    total_gross = entries.aggregate(Sum('gross'))

    for entry in entries:
        pct_employee = entry.gross / total_gross
        cs_for_employee = payment.total_amount * pct_employee

        for allocation in entry.allocations.all():
            allocation.social_charges_amount = cs_for_employee * (allocation.pct / 100)
            allocation.total_amount = allocation.net_amount + allocation.social_charges_amount
            allocation.social_charges_status = 'real'
            allocation.save()
```

### 9.5 Cálculo automático de billetes

```
denominations = [1000, 500, 200, 100, 50, 20, 10]
def calculate_bills(amount):
    bills = {}
    remaining = amount
    for d in denominations:
        bills[d] = remaining // d
        remaining = remaining % d
    return bills, remaining  # remaining debería ser 0 si net es múltiplo de 10
```

---

## 10. Roadmap de implementación

Construir en este orden, respetando dependencias:

### Fase 1 — Base (semanas 1-2)

- Setup proyecto Django + django-tenants + Postgres.
- App `core` con modelos abstractos y mixins.
- App `accounts` con User custom, registro, login HTML, recuperación.
- App `organizations` con Organization (tenant), Membership, Invitations.
- App `permissions` con Role, Permission constants, helpers, decoradores.
- Provisionamiento de tenant al crear Organization (signal).
- Provisionamiento de roles base al crear Organization.
- Layout base con Tailwind, sidebar, navegación.
- Tests de auth y multi-tenancy.

### Fase 2 — Catálogos (semana 3)

- App `catalog` con todos los modelos heredando de CatalogItem.
- CRUD HTML+HTMX para cada catálogo.
- Importador CSV/Excel por catálogo.
- App `projects` con Project, listados, detalle, CRUD.

### Fase 3 — Cotizaciones y precios base (semana 4)

- App `pricing` con ExchangeRate, Price, ExchangeRateType.
- CurrencyConversionService, PriceLookupService.
- UI de cotizaciones (cargar, ver histórico).
- Soporte para tipos calculados (70/30) automáticos.

### Fase 4 — Compras / KPS (semanas 5-6)

- App `procurement` con Purchase, PurchaseItem, PurchasePayment.
- Flujo Gestión: carga cabecera, abre ítems, confirma.
- Flujo Tesorería: ve compras, registra pagos.
- Signal: PurchaseItem → Price.
- Vistas separadas para compras de obra y administrativas.
- Importador histórico.

### Fase 5 — Nómina (semanas 7-9)

- App `payroll` con Employee, EmployeePersonalData, EmployeeBanking, EmergencyContact.
- PayrollPeriod, PositionPlus, PayrollEntry, PayrollAllocation, PayrollExtraordinary.
- UI tipo planilla para carga de quincena (HTMX inline editing).
- Cálculos automáticos (bruto, neto, billetes).
- Resumen de quincena (por equipo, por sociedad).
- Talonarios PDF.
- SocialChargesPayment + servicio de prorrateo.

### Fase 6 — Maestros (semanas 10-11)

- App `task_master` con Mix, MixComponent, Task, TaskComponent.
- Editor visual de recetas (con drag & drop opcional).
- TaskCostCalculator recursivo.
- Visualización de costo en tiempo real al editar.
- Soporte para sub-tareas y sub-mezclas con prevención de ciclos.

### Fase 7 — Seguimiento (semana 12)

- App `tracking` con TaskExecution, ProjectExecutionSnapshot, ProjectForecast.
- Servicio VarianceAnalyzer.
- Generación de TaskAdjustmentSuggestion (Celery job).
- UI de aprobación de sugerencias.
- Dashboard de obra con KPIs.

### Fase 8 — Presupuestos (semanas 13-14)

- App `budgets` con Budget, BudgetItem.
- Editor de presupuesto con cálculo en tiempo real.
- Snapshot al cerrar (receta + precios + cotización).
- Versionado (P1, P2, P3, superseded).
- PDF de presupuesto.

### Fase 9 — Análisis (semana 15)

- App `budget_analysis` con BudgetVsActualReport y servicio.
- Pantalla de cruce navegable.
- Exportación a Excel.

### Fase 10 — Tesorería (semanas 16-17)

- App `treasury` con TreasuryEntry.
- Signals desde Purchase, Payroll, SocialCharges.
- Cash flow, saldos por cuenta, conciliación.
- Cambio de monedas, transferencias.

### Fase 11 — Pulido (semanas 18-20)

- Reportes finales (todos los listados en sección 8).
- Importadores robustos con preview.
- Tests de integración end-to-end.
- Optimización de performance (queries, índices).
- Documentación de usuario.
- Onboarding wizard al crear org.

---

## 11. Decisiones por defecto a confirmar

Estas decisiones quedaron como default porque el usuario eligió "continuar sin responder" o no las respondió explícitamente. Antes de comenzar la implementación, revisar y confirmar:

| # | Tema | Default asumido |
|---|------|-----------------|
| 1 | Cantidad de obras por quincena | N obras (no limitado a 2). Tabla `PayrollAllocation` relacional. |
| 2 | Validación suma jornales = bruto | Sí, con tolerancia de centavos. |
| 3 | Conteo de billetes | Automático con override manual. |
| 4 | Moneda de sueldos | ARS por defecto pero el modelo soporta USD y otras. |
| 5 | Recibos legales | No, solo operativos. Los legales los hace otro sistema (Tango u otro). |
| 6 | Las compras actualizan precios automáticamente | Sí, con flag `is_reference` para excluir precios circunstanciales del cálculo de recetas. |
| 7 | Si hay varios precios cargados | El más reciente por timestamp con `is_reference=True`. Estrategia configurable. |
| 8 | Catálogo de tipos de subcontrato | Sí, hay un catálogo `Subcontract` aparte de Materiales. |
| 9 | Subcontrato por compra entera o por ítem | Por compra entera (`Purchase.is_subcontract`). |
| 10 | Cálculo de 70/30 | Automático desde BNA y CCL con override manual posible. |
| 11 | Significado de "Nocito" | Tipo de cotización custom (asumimos cambista). El usuario lo confirma al cargar. |
| 12 | Fecha sin cotización | Usar anterior más cercana (default 30 días) con warning visible. |
| 13 | Asistencia (columnas detalladas) | Incluye: días trabajados, faltas, justificadas, vacaciones, late hours, overtime. Si faltan columnas específicas, agregarlas. |

---

## 12. Estilo, diseño y convenciones

### Paleta de colores

| Nombre | Hex | Uso |
|--------|-----|-----|
| blue-mid | `#3d85c6` | Color primario. Botones principales, headers de tabla, links activos. |
| blue-light | `#9fc5e8` | Estados intermedios, hover, badges secundarios, bordes acentuados. |
| blue-pale | `#d0e2f3` | Backgrounds suaves, headers de sección, separadores. |
| white | `#ffffff` | Fondo principal. |
| gray-50 | `#f9fafb` | Fondo de tablas alternado. |
| gray-100 | `#f3f4f6` | Bordes suaves, dividers. |
| gray-700 | `#374151` | Texto principal. |
| gray-500 | `#6b7280` | Texto secundario. |
| red-500 | `#ef4444` | Errores, deletes. |
| green-500 | `#22c55e` | Éxito, aprobaciones. |
| amber-500 | `#f59e0b` | Advertencias, estados pendientes. |

Fondo siempre blanco. Headers y zonas destacadas usan blue-pale. Botones primarios blue-mid. Hover blue-light.

### Tipografía

- Sans-serif sistema: `Inter, ui-sans-serif, system-ui, -apple-system, sans-serif`
- Tamaños: 14px body, 16px headings, 12px metadata.
- Pesos: 400 regular, 500 medium, 600 semibold para headings.

### Convenciones Django

- Apps con nombres en singular o plural según convención (`accounts`, `procurement`, `payroll`).
- Modelos en singular (`Purchase`, `Employee`, no `Purchases`).
- Choices como `TextChoices` enum para legibilidad.
- Querysets custom y managers para `objects` filtrado por org.
- Signals en un archivo `signals.py` por app, registrados en `apps.py`.
- Servicios de negocio en `services.py` o módulo `services/` por app.
- Tests en `tests/` con `test_models.py`, `test_views.py`, `test_services.py`.

### Convenciones de UI

- URLs en kebab-case y en español donde tenga sentido para el dominio (`/obras/`, `/compras/`, `/quincenas/`).
- Internacionalizado desde día 1 con `gettext` (aunque inicialmente sea solo español).
- Fechas en formato DD/MM/YYYY para display, ISO para storage.
- Montos con separador de miles (.) y decimales con coma. Configurable por usuario.
- Toda tabla con paginación, búsqueda y exportar.
- Toda acción destructiva con confirmación modal.
- Loading states con HTMX `htmx-indicator`.

### Seguridad

- CSRF en todos los forms.
- Rate limiting en login (django-axes o similar).
- Passwords con hashers fuertes (Argon2 default de Django).
- Logs de auth fallidos.
- Audit log de cambios en modelos sensibles.
- Backup automático del schema de cada tenant (configurable).
- Variables sensibles en `.env`, nunca commiteadas.

### Performance

- Índices en columnas de filtro frecuente.
- `select_related` y `prefetch_related` en views de listado.
- Cache de cálculos pesados (cotizaciones del día, precios actuales) con TTL corto.
- Generación de reportes pesados con Celery.
- Paginación obligatoria en listados grandes (cursor pagination preferida).

---

## Notas finales para Claude Code

- Implementar siguiendo el roadmap fase por fase. No saltar fases.
- Antes de cada fase, leer y entender la sección de modelos correspondiente.
- Escribir tests con cada modelo y cada servicio crítico. Mínimo 70% de cobertura objetivo.
- Documentar decisiones tomadas durante la implementación en un CHANGELOG.
- Si surge ambigüedad no cubierta, marcar con TODO y consultar antes de improvisar.
- Priorizar legibilidad sobre cleverness.
- Commits pequeños y descriptivos en castellano o inglés (mantener consistencia).
