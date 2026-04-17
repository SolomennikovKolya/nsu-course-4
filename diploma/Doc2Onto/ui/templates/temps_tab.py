from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QInputDialog,
    QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Signal
from typing import Optional

from app.context import get_temp_manager
from app.settings import APP_NAME
from core.template.template import Template
from ui.templates.temp_info import TemplateInfoWidget


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    templates_changed = Signal()  # Сигнал, что список шаблонов изменился

    def __init__(self):
        super().__init__()

        self._temp_manager = get_temp_manager()
        self._temps_cache: list[Template] = []

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

        self._refresh_list()

    def _on_temp_added(self):
        name, ok = QInputDialog.getText(self, APP_NAME, "Название шаблона:")
        if not ok:
            return

        name = name.strip()
        if not name:
            return

        if name in self._temp_manager.doc_classes_list():
            QMessageBox.critical(self, APP_NAME, "Шаблон с таким именем уже существует.")
            return

        temp = self._temp_manager.add(name)
        self._refresh_list()
        self._select_temp_by_name(temp.name)
        self.templates_changed.emit()

    def _refresh_list(self):
        self._list.clear()
        self._temps_cache = self._temp_manager.list()
        for temp in self._temps_cache:
            self._list.addItem(temp.name)

    def _on_temp_selection_changed(self):
        temp = self._get_selected_temp()
        if temp is None:
            self._info_widget.set_template(None)
            return

        self._info_widget.set_template(temp)

    def _get_selected_temp(self) -> Optional[Template]:
        row = self._list.currentRow()
        if 0 <= row < len(self._temps_cache):
            return self._temps_cache[row]

        return None

    def _on_temp_name_changed(self):
        name = self._info_widget.current_template_name()
        self._refresh_list()
        if name:
            self._select_temp_by_name(name)

        self.templates_changed.emit()

    def _select_temp_by_name(self, name: str):
        """Устанавливает выбранный шаблон списка шаблонов по имени."""
        for i in range(self._list.count()):
            if self._list.item(i).text() == name:
                self._list.setCurrentRow(i)
                return

    def _on_temp_deleted(self):
        self._refresh_list()
        self._list.clearSelection()
        self._info_widget.set_template(None)
        self.templates_changed.emit()
