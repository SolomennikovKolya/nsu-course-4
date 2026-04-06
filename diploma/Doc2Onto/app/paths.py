"""Пути относительно корня приложения Doc2Onto (каталог с main.py, app/, data/)."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """Корень проекта."""
    return _ROOT
