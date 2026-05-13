from django.apps import AppConfig


class PayrollConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payroll"
    label = "payroll"
    verbose_name = "Nómina"

    def ready(self) -> None:  # noqa: D401
        from . import signals  # noqa: F401
