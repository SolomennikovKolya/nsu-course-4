"""Вкладка для управления шаблонами: список слева, информация и действия справа."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
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
from ui.templates.temp_list import TemplateListWidget


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    def __init__(self):
        super().__init__()
        self._temp_manager = get_temp_manager()
        self._build_ui()
        self._wire_signals()

    def _on_template_add(self):
        name, ok = QInputDialog.getText(self, APP_NAME, "Название шаблона:")
        name = name.strip()
        if not ok or not name:
            return

        if any(t.name == name for t in self._temp_manager.list()):
            QMessageBox.critical(self, APP_NAME, "Шаблон с таким именем уже существует.")
            return

        temp = self._temp_manager.add(name)
        self._list.add_or_update_template(temp, select=True)
        get_events().templates_changed.emit()

    def _on_template_name_changed(self, temp: Template):
        self._list.add_or_update_template(temp, select=True)
        get_events().templates_changed.emit()

    def _on_template_deleted(self):
        selected = self._list.current_template()
        if selected is not None:
            self._list.remove_template(selected)
        self._info.set_template(None)
        get_events().templates_changed.emit()

    def _build_ui(self):
        self._add_btn = QPushButton("Добавить шаблон")
        self._list = TemplateListWidget()

        left_panel = QWidget()
        left_panel.setMinimumWidth(MIN_LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._add_btn)
        left_layout.addWidget(self._list)

        self._info = TemplateInfoWidget()

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(self._info)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(SPLITTER_RATIO_SIZES)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def _wire_signals(self):
        self._add_btn.clicked.connect(self._on_template_add)
        self._list.template_selection_changed.connect(self._info.set_template)
        self._info.template_name_changed.connect(self._on_template_name_changed)
        self._info.template_deleted.connect(self._on_template_deleted)

        get_events().template_navigation_requested.connect(self._list.select_template_by_id)
