"""Códigos de permiso usados por todo el sistema.

Convención: SCOPE_ACCION. Se almacenan como string en Role.permissions (JSONField/list).
La verificación corre a través de helpers en `apps.permissions.checks`.
"""

# Obras / Projects
VIEW_PROJECTS = "view_projects"
EDIT_PROJECTS = "edit_projects"
MANAGE_PROJECTS = "manage_projects"

# Compras / Procurement
VIEW_PURCHASES = "view_purchases"
EDIT_PURCHASES = "edit_purchases"
EDIT_PURCHASE_ITEMS = "edit_purchase_items"
DELETE_PURCHASES = "delete_purchases"
VIEW_ADMIN_PURCHASES = "view_admin_purchases"
EDIT_ADMIN_PURCHASES = "edit_admin_purchases"
REGISTER_PAYMENTS = "register_payments"

# Nómina / Payroll
VIEW_PAYROLL = "view_payroll"
EDIT_PAYROLL = "edit_payroll"
CLOSE_PAYROLL = "close_payroll"
PAY_PAYROLL = "pay_payroll"
VIEW_EMPLOYEES = "view_employees"
EDIT_EMPLOYEES = "edit_employees"
VIEW_SENSITIVE_EMPLOYEE_DATA = "view_sensitive_employee_data"  # CBU, DNI
MANAGE_SOCIAL_CHARGES = "manage_social_charges"

# Maestros (Tareas / Mezclas)
VIEW_TASK_MASTER = "view_task_master"
EDIT_TASK_MASTER = "edit_task_master"
APPROVE_TASK_SUGGESTIONS = "approve_task_suggestions"

# Presupuestos / Budgets
VIEW_BUDGETS = "view_budgets"
EDIT_BUDGETS = "edit_budgets"
APPROVE_BUDGETS = "approve_budgets"

# Seguimiento / Tracking
VIEW_TRACKING = "view_tracking"

# Tesorería / Treasury
VIEW_TREASURY = "view_treasury"
EDIT_TREASURY = "edit_treasury"
RECONCILE_TREASURY = "reconcile_treasury"

# Precios / Pricing
VIEW_PRICING = "view_pricing"
EDIT_PRICING = "edit_pricing"

# Reportes
VIEW_REPORTS = "view_reports"
EXPORT_REPORTS = "export_reports"

# Administración de la organización
MANAGE_USERS = "manage_users"
MANAGE_ROLES = "manage_roles"
MANAGE_CATALOG = "manage_catalog"
MANAGE_ORGANIZATION = "manage_organization"


ALL_PERMISSIONS: tuple[str, ...] = (
    VIEW_PROJECTS, EDIT_PROJECTS, MANAGE_PROJECTS,
    VIEW_PURCHASES, EDIT_PURCHASES, EDIT_PURCHASE_ITEMS, DELETE_PURCHASES,
    VIEW_ADMIN_PURCHASES, EDIT_ADMIN_PURCHASES, REGISTER_PAYMENTS,
    VIEW_PAYROLL, EDIT_PAYROLL, CLOSE_PAYROLL, PAY_PAYROLL,
    VIEW_EMPLOYEES, EDIT_EMPLOYEES, VIEW_SENSITIVE_EMPLOYEE_DATA, MANAGE_SOCIAL_CHARGES,
    VIEW_TASK_MASTER, EDIT_TASK_MASTER, APPROVE_TASK_SUGGESTIONS,
    VIEW_BUDGETS, EDIT_BUDGETS, APPROVE_BUDGETS,
    VIEW_TRACKING,
    VIEW_TREASURY, EDIT_TREASURY, RECONCILE_TREASURY,
    VIEW_PRICING, EDIT_PRICING,
    VIEW_REPORTS, EXPORT_REPORTS,
    MANAGE_USERS, MANAGE_ROLES, MANAGE_CATALOG, MANAGE_ORGANIZATION,
)
