from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organizations"
    label = "organizations"
    verbose_name = "Organizaciones"

    def ready(self) -> None:  # noqa: D401
        from . import signals  # noqa: F401
