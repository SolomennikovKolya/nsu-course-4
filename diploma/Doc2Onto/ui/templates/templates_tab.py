"""Вкладка для управления шаблонами: список слева, информация и действия справа."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.context import get_events, get_temp_manager
from app.settings import APP_NAME, MIN_LEFT_PANEL_WIDTH, SPLITTER_RATIO_SIZES
from models.template import Template
from ui.templates.temp_info import TemplateInfoWidget


class TemplatesCache:
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


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    def __init__(self):
        super().__init__()
        self._temp_manager = get_temp_manager()
        self._cache = TemplatesCache()
        self._cache.load(self._temp_manager.list())
        self._build_ui()
        self._wire_signals()
        self._refresh_list()

    def _on_temp_added(self):
        name, ok = QInputDialog.getText(self, APP_NAME, "Название шаблона:")
        name = name.strip()
        if not ok or not name:
            return

        if any(t.name == name for t in self._temp_manager.list()):
            QMessageBox.critical(self, APP_NAME, "Шаблон с таким именем уже существует.")
            return

        temp = self._temp_manager.add(name)
        self._cache.add_or_update(temp)
        self._refresh_list(temp_to_select=temp.id)
        get_events().templates_changed.emit()

    def _on_temp_selection_changed(self):
        temp = self._selected_template()
        self._info_widget.set_template(temp)

    def _on_temp_name_changed(self, temp: Template):
        self._cache.add_or_update(temp)
        self._refresh_list(temp_to_select=temp.id)
        get_events().templates_changed.emit()

    def _on_temp_deleted(self):
        selected = self._selected_template()
        if selected is not None:
            self._cache.remove(selected)

        self._refresh_list()
        self._list.clearSelection()
        self._info_widget.set_template(None)
        get_events().templates_changed.emit()

    def _on_template_navigation_requested(self, template_id: str):
        """Активирует элемент списка для шаблона с заданным id (если найден)."""
        for i, temp in enumerate(self._cache.items()):
            if temp.id == template_id:
                self._list.setCurrentRow(i)
                return

    def _selected_template(self) -> Template | None:
        return self._cache.get_by_index(self._list.currentRow())

    def _refresh_list(self, temp_to_select: str | None = None):
        self._list.clear()
        for i, temp in enumerate(self._cache.items()):
            self._list.addItem(temp.name)
            if temp.id == temp_to_select:
                self._list.setCurrentRow(i)

    def _build_ui(self):
        self._add_btn = QPushButton("Добавить шаблон")
        self._list = QListWidget()

        left_panel = QWidget()
        left_panel.setMinimumWidth(MIN_LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._add_btn)
        left_layout.addWidget(self._list)

        self._info_widget = TemplateInfoWidget()

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(self._info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(SPLITTER_RATIO_SIZES)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

    def _wire_signals(self):
        self._add_btn.clicked.connect(self._on_temp_added)
        self._list.itemSelectionChanged.connect(self._on_temp_selection_changed)
        self._info_widget.template_name_changed.connect(self._on_temp_name_changed)
        self._info_widget.template_deleted.connect(self._on_temp_deleted)

        get_events().template_navigation_requested.connect(self._on_template_navigation_requested)
