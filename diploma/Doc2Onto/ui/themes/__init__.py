"""Темы оформления UI (светлая / тёмная)."""

from ui.themes.base import BaseAppTheme
from ui.themes.dark import DarkTheme
from ui.themes.light import LightTheme
from ui.themes.manager import THEME_REGISTRY, ThemeManager

__all__ = [
    "THEME_REGISTRY",
    "BaseAppTheme",
    "DarkTheme",
    "LightTheme",
    "ThemeManager",
]
