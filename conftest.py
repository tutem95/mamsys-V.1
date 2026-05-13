"""Configuración global de pytest."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _media_storage(settings, tmp_path):
    """Aislar media en cada test para evitar contaminación."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
