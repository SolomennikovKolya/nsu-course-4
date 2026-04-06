from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QInputDialog,
    QSplitter,
)
from PySide6.QtCore import Signal
from typing import Optional

from app.context import get_temp_manager
from core.template.template import Template
from ui.templates.template_info import TemplateInfoWidget
from ui.common.utils import show_warning_dialog


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    templates_changed = Signal()  # Сигнал, что список шаблонов изменился

    def __init__(self):
        super().__init__()

        self.temp_manager = get_temp_manager()
        self.templates_cache: list[Template] = []

        # --- Список шаблонов ---
        self.add_button = QPushButton("Добавить шаблон")
        self.list_widget = QListWidget()

        left_widget = QWidget()
        left_widget.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self.add_button)
        left_layout.addWidget(self.list_widget)

        # --- Информация о шаблоне ---
        self.info_widget = TemplateInfoWidget()

        # --- Основной макет ---
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(self.info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # --- Сигналы ---
        self.add_button.clicked.connect(self.add_template)
        self.list_widget.itemSelectionChanged.connect(self.update_info)
        self.info_widget.template_name_changed.connect(self._on_template_name_changed)
        self.info_widget.template_deleted.connect(self._on_template_deleted)

        self.refresh_templates_list()

    def refresh_templates_list(self):
        self.list_widget.clear()
        self.templates_cache = self.temp_manager.list()
        for t in self.templates_cache:
            self.list_widget.addItem(t.name)

    def add_template(self):
        name, ok = QInputDialog.getText(self, "Добавить шаблон", "Название шаблона:")
        if not ok:
            return

        name = name.strip()
        if not name:
            return

        if name in self.temp_manager.doc_classes_list():
            show_warning_dialog(self, "Шаблон с таким именем уже существует.", "Ошибка добавления шаблона")
            return

        t = self.temp_manager.add(name)
        self.refresh_templates_list()
        self._select_template_by_name(t.name)
        self.templates_changed.emit()

    def get_selected_template(self) -> Optional[Template]:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.templates_cache):
            return self.templates_cache[row]
        return None

    def update_info(self):
        t = self.get_selected_template()
        if t is None:
            self.info_widget.set_template(None)
            return
        self.info_widget.set_template(t)

    def _select_template_by_name(self, name: str):
        """Устанавливает выбранный шаблон списка шаблонов по имени."""
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == name:
                self.list_widget.setCurrentRow(i)
                return

    def _on_template_name_changed(self):
        name = self.info_widget.current_template_name()
        self.refresh_templates_list()
        if name:
            self._select_template_by_name(name)
        self.templates_changed.emit()

    def _on_template_deleted(self):
        self.refresh_templates_list()
        self.list_widget.clearSelection()
        self.info_widget.set_template(None)
        self.templates_changed.emit()
