"""Главное окно приложения, содержащее вкладки для управления документами, шаблонами и онтологией."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.context import get_theme_manager
from app.settings import APP_NAME, MAIN_WINDOW_H, MAIN_WINDOW_W
from ui.documents.documents_tab import DocumentsTab
from ui.ontology.ontology_tab import OntologyTab
from ui.settings.settings_tab import SettingsTab
from ui.templates.templates_tab import TemplatesTab


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами, шаблонами и онтологией."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(MAIN_WINDOW_W, MAIN_WINDOW_H)

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

        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._docs_tab.ontology_changed.connect(self._onto_tab.refresh_graph)
        self._temps_tab.templates_changed.connect(self._docs_tab.refresh_templates)
        self._onto_tab.document_navigation_requested.connect(self._on_document_navigation_requested)
        self._onto_tab.template_navigation_requested.connect(self._on_template_navigation_requested)
        get_theme_manager().theme_changed.connect(self._on_global_theme_changed)

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._docs_tab:
            self._docs_tab.refresh_templates()
        elif self._tabs.widget(index) is self._onto_tab:
            self._onto_tab.refresh_graph()

    def _on_document_navigation_requested(self, doc_id: str):
        self._tabs.setCurrentWidget(self._docs_tab)
        self._docs_tab.select_document_by_id(doc_id)

    def _on_template_navigation_requested(self, template_id: str):
        self._tabs.setCurrentWidget(self._temps_tab)
        self._temps_tab.select_template_by_id(template_id)

    def _on_global_theme_changed(self, _theme_id: str):
        self._docs_tab.apply_theme()
        self._temps_tab.apply_theme()
        self._onto_tab.apply_theme()
        self._settings_tab.apply_external_theme_change()
