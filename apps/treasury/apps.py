from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.treasury"
    label = "treasury"
    verbose_name = "Tesorería"

    def ready(self) -> None:  # noqa: D401
        from . import signals  # noqa: F401
