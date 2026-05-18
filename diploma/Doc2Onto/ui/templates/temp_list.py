"""Список шаблонов: собственный кеш и API для управления выделением."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QVBoxLayout, QWidget

from app.context import get_temp_manager
from models.template import Template


class _TemplatesCache:
    """Кеш шаблонов для быстрого обновления списка без чтения с диска."""

    def __init__(self):
        self._items: list[Template] = []

    def load(self, templates: list[Template]):
        self._items = sorted(templates, key=lambda t: t.name.lower())

    def items(self) -> list[Template]:
        return self._items

    def get_by_index(self, index: int) -> Template | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def add_or_update(self, template: Template):
        self.remove(template)
        self._items.append(template)
        self._items.sort(key=lambda t: t.name.lower())

    def remove(self, template: Template):
        self._items = [t for t in self._items if t is not template and t.id != template.id]


class TemplateListWidget(QWidget):
    """Список шаблонов с собственным кешем."""

    template_selection_changed = Signal(object)  # Template | None

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._temp_manager = get_temp_manager()
        self._cache = _TemplatesCache()
        self._cache.load(self._temp_manager.list())
        self._build_ui()
        self._wire_signals()
        self._refresh_list()

    def add_or_update_template(self, template: Template, *, select: bool = False):
        """Добавить или обновить шаблон; при ``select=True`` выделить его в списке."""
        self._cache.add_or_update(template)
        self._refresh_list(template_to_select=template.id if select else None)

    def remove_template(self, template: Template):
        self._cache.remove(template)
        self._refresh_list()
        self._list.clearSelection()

    def current_template(self) -> Template | None:
        """Возвращает выделенный шаблон или ``None``."""
        return self._cache.get_by_index(self._list.currentRow())

    def select_template_by_id(self, template_id: str) -> bool:
        """Выделить шаблон по id; возвращает ``True``, если шаблон найден."""
        for i, temp in enumerate(self._cache.items()):
            if temp.id == template_id:
                self._list.setCurrentRow(i)
                return True
        return False

    def _on_selection_changed(self):
        self.template_selection_changed.emit(self.current_template())

    def _build_ui(self):
        self._list = QListWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)

    def _wire_signals(self):
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

    def _refresh_list(self, template_to_select: str | None = None):
        self._list.clear()
        for i, temp in enumerate(self._cache.items()):
            self._list.addItem(temp.name)
            if temp.id == template_to_select:
                self._list.setCurrentRow(i)
