import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mamsys.settings.dev")

app = Celery("mamsys")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
