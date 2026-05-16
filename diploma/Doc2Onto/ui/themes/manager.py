from __future__ import annotations

import json
from typing import Dict, Type

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.settings import UI_SETTINGS_PATH
from ui.themes.base import BaseAppTheme
from ui.themes.dark import DarkTheme
from ui.themes.light import LightTheme

THEME_REGISTRY: Dict[str, Type[BaseAppTheme]] = {
    DarkTheme.theme_id: DarkTheme,
    LightTheme.theme_id: LightTheme,
}


class ThemeManager(QObject):
    """
    Менеджер тем: загрузка/сохранение, применение к QApplication, сигнал смены.
    Текущая тема, персистентность в ``ui_settings.json``, применение глобального QSS.
    """

    theme_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._theme_id: str = LightTheme.theme_id  # Идентификатор текущей темы
        self._app: QApplication | None = None      # Приложение, к которому применяется тема
        self._load()

    def _load(self):
        if not UI_SETTINGS_PATH.exists():
            return
        try:
            raw = json.loads(UI_SETTINGS_PATH.read_text(encoding="utf-8"))
            tid = raw.get("theme_id")
            if isinstance(tid, str) and tid in THEME_REGISTRY:
                self._theme_id = tid
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self):
        try:
            UI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            UI_SETTINGS_PATH.write_text(
                json.dumps({"theme_id": self._theme_id}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    @property
    def theme_id(self) -> str:
        """Идентификатор текущей темы."""
        return self._theme_id

    @property
    def current(self) -> BaseAppTheme:
        """Текущая тема."""
        cls = THEME_REGISTRY.get(self._theme_id, LightTheme)
        return cls()

    def available_themes(self) -> list[tuple[str, str]]:
        """Список ``(theme_id, display_name)``."""
        return [(cls.theme_id, cls.display_name) for cls in THEME_REGISTRY.values()]

    def attach_application(self, app: QApplication):
        """Прикрепить приложение к менеджеру тем."""
        self._app = app
        self.apply_current()

    def set_theme_id(self, theme_id: str, *, persist: bool = True):
        """Установить идентификатор темы. persist=True - сохранить тему в файл."""
        if theme_id not in THEME_REGISTRY:
            return
        if theme_id == self._theme_id:
            return

        self._theme_id = theme_id
        if persist:
            self._save()

        self.apply_current()
        self.theme_changed.emit(self._theme_id)

    def apply_current(self):
        """Применить текущую глобальную таблицу стилей к приложению."""
        if self._app is None:
            return

        self._app.setStyleSheet(self.current.global_application_stylesheet())
