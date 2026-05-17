"""
Хелперы для работы с динамическими свойствами Qt (property-селекторами QSS).

Используются вместо inline ``setStyleSheet(...)``. Семантика хранится в свойстве,
цвета и оформление — в глобальном QSS темы (см. ``BaseAppTheme``).

Пример:
    set_role(self._hint_label, "muted")     # → QSS селектор QLabel[role="muted"]
    set_severity(self._step, "success")     # → QSS селектор QLabel[severity="success"]
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def set_role(widget: QWidget, role: str | None):
    """Назначить динамическое свойство ``role`` и перерисовать стиль."""
    widget.setProperty("role", role)
    _repolish(widget)


def set_severity(widget: QWidget, severity: str | None):
    """Назначить динамическое свойство ``severity`` и перерисовать стиль."""
    widget.setProperty("severity", severity)
    _repolish(widget)


def set_state(widget: QWidget, key: str, value: str | bool | None):
    """Универсальный сеттер: назначить произвольное property и перерисовать стиль."""
    widget.setProperty(key, value)
    _repolish(widget)


def _repolish(widget: QWidget):
    """Перерасчитать стиль виджета после смены динамических свойств."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
