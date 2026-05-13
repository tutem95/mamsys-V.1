from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.procurement"
    label = "procurement"
    verbose_name = "Compras"

    def ready(self) -> None:  # noqa: D401
        from . import signals  # noqa: F401
