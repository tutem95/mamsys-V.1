"""Servicios de permisos."""

from __future__ import annotations

from . import constants as P
from .models import Role


# Definición de los roles base que se crean al provisionar una organización.
DEFAULT_ROLES: dict[str, dict] = {
    "Admin": {
        "description": "Acceso total a la organización.",
        "permissions": list(P.ALL_PERMISSIONS),
    },
    "Área Técnica / Gestión": {
        "description": "Carga compras, abre facturas en ítems, edita maestros, ve seguimiento.",
        "permissions": [
            P.VIEW_PROJECTS, P.EDIT_PROJECTS,
            P.VIEW_PURCHASES, P.EDIT_PURCHASES, P.EDIT_PURCHASE_ITEMS,
            P.VIEW_TASK_MASTER, P.EDIT_TASK_MASTER, P.APPROVE_TASK_SUGGESTIONS,
            P.VIEW_TRACKING,
            P.VIEW_BUDGETS, P.EDIT_BUDGETS,
            P.VIEW_PRICING,
            P.VIEW_EMPLOYEES,
            P.VIEW_REPORTS, P.EXPORT_REPORTS,
            P.MANAGE_CATALOG,
        ],
    },
    "Tesorería": {
        "description": "Gestiona pagos y movimientos. Ve compras de obra en solo-lectura.",
        "permissions": [
            P.VIEW_PROJECTS,
            P.VIEW_PURCHASES, P.REGISTER_PAYMENTS,
            P.VIEW_ADMIN_PURCHASES, P.EDIT_ADMIN_PURCHASES,
            P.VIEW_TREASURY, P.EDIT_TREASURY, P.RECONCILE_TREASURY,
            P.MANAGE_SOCIAL_CHARGES,
            P.VIEW_PAYROLL,
            P.VIEW_PRICING,
            P.VIEW_REPORTS, P.EXPORT_REPORTS,
        ],
    },
    "RRHH / Nómina": {
        "description": "Gestiona empleados, quincenas y pagos de sueldos.",
        "permissions": [
            P.VIEW_EMPLOYEES, P.EDIT_EMPLOYEES, P.VIEW_SENSITIVE_EMPLOYEE_DATA,
            P.VIEW_PAYROLL, P.EDIT_PAYROLL, P.CLOSE_PAYROLL, P.PAY_PAYROLL,
            P.VIEW_PROJECTS,
            P.VIEW_REPORTS, P.EXPORT_REPORTS,
        ],
    },
    "Solo Lectura": {
        "description": "Ve dashboards y reportes; no edita.",
        "permissions": [
            P.VIEW_PROJECTS,
            P.VIEW_PURCHASES,
            P.VIEW_PAYROLL, P.VIEW_EMPLOYEES,
            P.VIEW_TASK_MASTER,
            P.VIEW_BUDGETS, P.VIEW_TRACKING,
            P.VIEW_TREASURY, P.VIEW_PRICING,
            P.VIEW_REPORTS,
        ],
    },
}


def create_default_roles(organization) -> list[Role]:
    """Crea los Roles base para una Organization recién provisionada."""
    created: list[Role] = []
    for name, cfg in DEFAULT_ROLES.items():
        role, _ = Role.objects.get_or_create(
            organization=organization,
            name=name,
            defaults={
                "description": cfg["description"],
                "permissions": cfg["permissions"],
                "is_system": True,
            },
        )
        created.append(role)
    return created
