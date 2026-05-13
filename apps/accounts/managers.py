from __future__ import annotations

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Manager para el User custom basado en email (sin username)."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified", True)
        if not extra_fields.get("is_staff"):
            raise ValueError("Un superusuario debe tener is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Un superusuario debe tener is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
