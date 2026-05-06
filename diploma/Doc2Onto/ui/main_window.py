from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.documents.main_tab import DocumentsTab
from ui.templates.temps_tab import TemplatesTab
from ui.ontology.main_tab import OntologyTab


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами, шаблонами и онтологией."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doc2Onto")
        self.resize(900, 600)

        self._tabs = QTabWidget()

        self._docs_tab = DocumentsTab()
        self._tabs.addTab(self._docs_tab, "Документы")

        self._temps_tab = TemplatesTab()
        self._tabs.addTab(self._temps_tab, "Шаблоны")

        self._onto_tab = OntologyTab()
        self._tabs.addTab(self._onto_tab, "Модель")

        self.setCentralWidget(self._tabs)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._temps_tab.templates_changed.connect(self._docs_tab.refresh_templates)

        self._docs_tab.ontology_changed.connect(self._onto_tab.refresh_graph)
        self._onto_tab.document_navigation_requested.connect(self._on_document_navigation_requested)
        self._onto_tab.template_navigation_requested.connect(self._on_template_navigation_requested)

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
