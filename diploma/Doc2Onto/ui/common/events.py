"""Шина доменных событий UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppEvents(QObject):
    """
    Доменные события, на которые могут подписаться любые виджеты UI.

    Принцип: сигнал испускается *после* того, как доменное состояние обновлено
    в соответствующем менеджере. Подписчики читают актуальное состояние
    из менеджеров и не зависят от порядка вызова друг друга.
    """

    # Шаблоны: список или содержимое шаблонов изменилось
    templates_changed = Signal()

    # Онтология: модель пересобрана (документ добавлен/откачен/удалён, изменена политика и т.п.)
    ontology_changed = Signal()

    # Навигация между вкладками (используется карточками онтологии и др.)
    document_navigation_requested = Signal(str)  # doc_id
    template_navigation_requested = Signal(str)  # template_id
