from django.apps import AppConfig


class BudgetAnalysisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.budget_analysis"
    label = "budget_analysis"
    verbose_name = "Análisis de presupuesto"
