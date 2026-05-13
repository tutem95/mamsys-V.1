# Mamsys V.1

SaaS multi-tenant para constructoras pyme argentinas. Reemplaza un ecosistema de planillas de Google Sheets con gestión integral de compras, nómina, obras, presupuestos, tesorería y multi-moneda.

> **Spec completa:** [docs/SPEC.md](docs/SPEC.md). Es la fuente de verdad del proyecto.

## Stack

- Python 3.11+ / Django 5
- PostgreSQL 16 (django-tenants, schema por organización)
- HTMX + Alpine.js + Tailwind CSS
- Celery + Redis
- django-allauth, django-rules, DRF
- WeasyPrint (PDF), openpyxl (Excel)
- pytest + factory-boy

## Setup local

### Requisitos previos

- Python 3.11+ (la spec pide 3.12+; 3.11 sirve por ahora).
- PostgreSQL 16+ y Redis 7+, ya sea instalados nativamente o via Docker.
- Node 20+ (opcional, solo para compilar Tailwind).

### 1. Levantar servicios

Con Docker:

```bash
docker compose up -d
```

O instalar Postgres y Redis nativamente y apuntar las URLs del `.env`.

### 2. Entorno Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
```

### 3. Migraciones (django-tenants)

```bash
python manage.py migrate_schemas --shared
python manage.py createsuperuser
```

### 4. Correr el server

```bash
python manage.py runserver
```

### 5. Tests

```bash
pytest
```

## Estructura

```
mamsys-V.1/
├── apps/                  # Apps Django de negocio (1 por dominio)
│   ├── core/              # Modelos abstractos y mixins
│   ├── accounts/          # User custom + auth
│   ├── organizations/     # Tenants, Sociedades, Memberships
│   ├── permissions/       # Roles, permisos por sección y por objeto
│   └── ...                # catalog, projects, procurement, payroll, etc.
├── mamsys/                # Configuración del proyecto Django
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/             # Templates base (Tailwind + HTMX)
├── static/                # Assets compilados
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── docs/
│   └── SPEC.md            # Especificación funcional y técnica
├── docker-compose.yml
├── pyproject.toml
├── manage.py
└── README.md
```

## Roadmap

Ver sección 10 del [SPEC](docs/SPEC.md). Las fases se construyen en orden:

1. **Fase 1 (en progreso):** Base — auth, tenancy, roles, layout.
2. Fase 2: Catálogos + Projects.
3. Fase 3: Cotizaciones y precios.
4. Fase 4: Compras (KPS).
5. Fase 5: Nómina.
6. Fase 6: Maestros (Tareas/Mezclas).
7. Fase 7: Seguimiento.
8. Fase 8: Presupuestos.
9. Fase 9: Análisis (cruce real vs presupuesto).
10. Fase 10: Tesorería.
11. Fase 11: Pulido y reportes.

## Convenciones

- URLs en español kebab-case (`/obras/`, `/compras/`, `/quincenas/`).
- Commits descriptivos. Tests con cada modelo o servicio crítico (≥70% cobertura).
- Lint y format con `ruff`.
- Si surge ambigüedad fuera del SPEC: marcar TODO y consultar antes de improvisar.

## Licencia

Propietaria. Todos los derechos reservados.
