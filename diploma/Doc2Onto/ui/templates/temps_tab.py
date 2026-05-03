from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QPushButton,
    QInputDialog, QSplitter, QMessageBox
)

from app.context import get_temp_manager
from app.settings import APP_NAME
from models.template import Template
from ui.templates.temp_info import TemplateInfoWidget


class TemplatesCache:
    """Кеш шаблонов для быстрого обновления списка без чтения с диска."""

    def __init__(self):
        self._items: list[Template] = []

    def load(self, templates: list[Template]):
        self._items = list(templates)

    def items(self) -> list[Template]:
        return self._items

    def get_by_index(self, index: int) -> Optional[Template]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def add_or_update(self, template: Template):
        self.remove(template)
        self._items.append(template)

    def remove(self, template: Template):
        self._items = [t for t in self._items if t is not template and t.id != template.id]


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    templates_changed = Signal()  # Сигнал, что список шаблонов изменился

    def __init__(self):
        super().__init__()
        self._temp_manager = get_temp_manager()
        self._temps_cache = TemplatesCache()

        # --- Список шаблонов ---
        add_button = QPushButton("Добавить шаблон")
        self._list = QListWidget()

        list_widget = QWidget()
        list_widget.setMinimumWidth(250)
        list_layout = QVBoxLayout(list_widget)
        list_layout.addWidget(add_button)
        list_layout.addWidget(self._list)

        # --- Информация о шаблоне ---
        self._info_widget = TemplateInfoWidget()

        # --- Основной макет ---
        splitter = QSplitter()
        splitter.addWidget(list_widget)
        splitter.addWidget(self._info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # --- Сигналы ---
        add_button.clicked.connect(self._on_temp_added)
        self._list.itemSelectionChanged.connect(self._on_temp_selection_changed)
        self._info_widget.template_name_changed.connect(self._on_temp_name_changed)
        self._info_widget.template_deleted.connect(self._on_temp_deleted)

        self._load_temps_cache()
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
        self._temps_cache.add_or_update(temp)
        self._refresh_list(temp_to_select=temp.id)
        self.templates_changed.emit()

    def _refresh_list(self, temp_to_select: Optional[str] = None):
        self._list.clear()
        for i, temp in enumerate(self._temps_cache.items()):
            self._list.addItem(temp.name)
            if temp.id == temp_to_select:
                self._list.setCurrentRow(i)

    def _on_temp_selection_changed(self):
        temp = self._get_selected_temp()
        if temp is None:
            self._info_widget.set_template(None)
            return

        self._info_widget.set_template(temp)

    def _get_selected_temp(self) -> Optional[Template]:
        row = self._list.currentRow()
        return self._temps_cache.get_by_index(row)

    def _on_temp_name_changed(self, temp: Template):
        self._temps_cache.add_or_update(temp)
        self._refresh_list(temp_to_select=temp.id)
        self.templates_changed.emit()

    def _on_temp_deleted(self):
        selected_temp = self._get_selected_temp()
        if selected_temp is not None:
            self._temps_cache.remove(selected_temp)

        self._refresh_list()
        self._list.clearSelection()
        self._info_widget.set_template(None)
        self.templates_changed.emit()

    def _load_temps_cache(self):
        self._temps_cache.load(self._temp_manager.list())
