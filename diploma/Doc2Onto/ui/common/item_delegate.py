"""
Делегат семантической раскраски элементов QTreeWidget / QTableWidget.

Семантическая роль элемента хранится в ``ITEM_KIND_ROLE`` (произвольная строка,
например ``"link_class"`` или ``"severity_error"``). Цвет берётся из текущей темы
через ``BaseAppTheme.color_for_item_kind(kind)``.

Делегат сам перерисовывает свой view при смене темы — никаких ручных
``viewport().update()`` в виджете писать не нужно.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from app.context import get_theme_manager

# Семантическая роль элемента — строка из словаря ``BaseAppTheme.color_for_item_kind``.
ITEM_KIND_ROLE = Qt.ItemDataRole.UserRole + 100


class ThemedItemDelegate(QStyledItemDelegate):
    """Раскрашивает текст элементов согласно ``ITEM_KIND_ROLE`` и текущей теме."""

    def __init__(self, parent: QAbstractItemView):
        super().__init__(parent)
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    def paint(self, painter, option: QStyleOptionViewItem, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        kind = index.data(ITEM_KIND_ROLE)
        if isinstance(kind, str) and not (opt.state & QStyle.StateFlag.State_Selected):
            color_value = get_theme_manager().current.color_for_item_kind(kind)
            if color_value:
                opt.palette.setColor(QPalette.ColorRole.Text, QColor(color_value))

        super().paint(painter, opt, index)

    def _on_theme_changed(self, _theme_id: str):
        view = self.parent()
        if isinstance(view, QAbstractItemView):
            view.viewport().update()
