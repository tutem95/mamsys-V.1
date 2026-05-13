# Changelog

Decisiones de implementación que no son obvias del código y vale la pena registrar para el futuro.

## [Unreleased] — Fase 1 (Base)

### Decisiones de arquitectura

- **Role vive en SHARED (schema `public`)**, no en TENANT. Razón: Membership es shared (un usuario puede pertenecer a varias orgs) y necesita FK a Role. Mantener ambos en `public` evita FK cross-schema, que django-tenants no soporta. La spec era ambigua acá.
- **Se descartó `OrganizationOwnedModel` con FK a Organization en TENANT_APPS.** Mismo motivo: cross-schema FK. Con django-tenants la tenancy ya está dada por el schema, así que el campo es redundante. Si surge un caso de cross-tenant reporting, se reintroduce con `organization_id` plano (sin FK de DB).
- **`AUTH_USER_MODEL` en SHARED.** El email es identidad global del SaaS: un usuario que asesora a varias constructoras tiene una sola cuenta.
- **Sign-up de organización se hace en el schema PUBLIC**, no en el del tenant (el tenant todavía no existe). El servicio crea User + Organization (con auto-schema) + Domain + Membership en una transacción.
- **Tailwind via CDN para Fase 1.** Decidido para evitar agregar toolchain Node hasta tener una primera versión navegable. Reemplazar por build compilado en Fase 11 (pulido).
- **Login flow usa allauth con templates propios.** El sign-up de allauth está deshabilitado (`ACCOUNT_SIGNUP_FIELDS` se usa solo para login); las orgs nuevas se crean por el flujo en `apps.organizations`.
- **`ObjectAccess` usa `GenericForeignKey` sin FK de DB.** Apunta a objetos que viven en schemas de tenant, así que el target se resuelve en runtime dentro del schema corriente.

### Pendientes de Fase 1 (no bloqueantes)

- Verificación de email obligatoria en prod (en dev queda `optional`).
- Wizard de creación de Company (Sociedad) tras crear la Organization.
- Tests de tenancy end-to-end (necesitan Postgres corriendo).
- Sustituir Tailwind CDN por build compilado.
- Vista de selección de organización para usuarios con múltiples memberships.

### Decisiones por defecto pendientes de confirmar (ver SPEC §11)

Marcados acá para no perderlos:

- §11.1 N obras por quincena (default asumido).
- §11.2 Validación suma jornales = bruto con tolerancia.
- §11.6 Compras alimentan precios automáticamente con flag `is_reference`.
- §11.9 Subcontrato por compra entera (no por ítem).
- §11.10 70/30 calculado automáticamente desde BNA y CCL.

Conviene firmar estas decisiones antes de iniciar Fase 4 (Compras) y Fase 5 (Nómina).
