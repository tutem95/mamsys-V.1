from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-not-for-production")
ALLOWED_HOSTS = ["*"]

# Django debug toolbar (no-op si no está instalado)
if DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(
            MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,
            "debug_toolbar.middleware.DebugToolbarMiddleware",
        )
        INTERNAL_IPS = ["127.0.0.1"]
    except ImportError:
        pass

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ACCOUNT_EMAIL_VERIFICATION = "optional"
