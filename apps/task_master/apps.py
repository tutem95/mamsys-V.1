from django.apps import AppConfig


class TaskMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.task_master"
    label = "task_master"
    verbose_name = "Maestros (Tareas y Mezclas)"
