"""Главное окно приложения: вкладки документов, шаблонов, онтологии и настроек."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.context import get_events
from app.settings import APP_NAME, MAIN_WINDOW_H, MAIN_WINDOW_W
from ui.documents.documents_tab import DocumentsTab
from ui.ontology.ontology_tab import OntologyTab
from ui.settings.settings_tab import SettingsTab
from ui.templates.templates_tab import TemplatesTab


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(MAIN_WINDOW_W, MAIN_WINDOW_H)
        self._build_ui()
        self._wire_signals()

    def _on_document_navigation_requested(self, _doc_id: str):
        self._tabs.setCurrentWidget(self._docs_tab)

    def _on_template_navigation_requested(self, _template_id: str):
        self._tabs.setCurrentWidget(self._temps_tab)

    def _build_ui(self):
        self._tabs = QTabWidget()
        self._docs_tab = DocumentsTab()
        self._temps_tab = TemplatesTab()
        self._onto_tab = OntologyTab()
        self._settings_tab = SettingsTab()
        self._tabs.addTab(self._docs_tab, "Документы")
        self._tabs.addTab(self._temps_tab, "Шаблоны")
        self._tabs.addTab(self._onto_tab, "Модель")
        self._tabs.addTab(self._settings_tab, "Настройки")
        self.setCentralWidget(self._tabs)

    def _wire_signals(self):
        # MainWindow слушает шину только ради переключения активной вкладки;
        # сам выбор элемента делает соответствующая вкладка в своём обработчике.
        events = get_events()
        events.document_navigation_requested.connect(self._on_document_navigation_requested)
        events.template_navigation_requested.connect(self._on_template_navigation_requested)
