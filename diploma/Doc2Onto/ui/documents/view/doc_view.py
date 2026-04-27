from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from models.document import Document
from ui.documents.view.common import wrap_tab_page_content
from ui.documents.view.fields_tab import DocumentViewFieldsTab
from ui.documents.view.original_tab import DocumentViewOriginalTab
from ui.documents.view.rdf_tab import DocumentViewRdfTab
from ui.documents.view.uddm_tab import DocumentViewUddmTab


class DocumentViewWidget(QWidget):
    """Вкладки предпросмотра документа и его промежуточных данных."""

    validation_result_changed = Signal(Document)

    def __init__(self):
        super().__init__()

        self._document: Optional[Document] = None
        self._tabs = QTabWidget()
        self._original_tab = DocumentViewOriginalTab()
        self._uddm_tab = DocumentViewUddmTab()
        self._fields_tab = DocumentViewFieldsTab()
        self._rdf_tab = DocumentViewRdfTab()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tabs)

        self._tabs.addTab(wrap_tab_page_content(self._original_tab), "Оригинал")
        self._tabs.addTab(self._uddm_tab, "UDDM")
        self._tabs.addTab(wrap_tab_page_content(self._fields_tab), "Поля")
        self._tabs.addTab(wrap_tab_page_content(self._rdf_tab), "RDF")
        self._apply_no_document_state()

        # --- Сигналы ---
        self._fields_tab.validation_result_changed.connect(self._on_validation_result_changed)

    def set_document(self, document: Optional[Document]):
        """Установка текущего документа в виджет."""
        self._document = document
        self._tabs.setTabEnabled(0, self._original_tab.set_document(document))
        self._tabs.setTabEnabled(1, self._uddm_tab.set_document(document))
        self._tabs.setTabEnabled(2, self._fields_tab.set_document(document))
        self._tabs.setTabEnabled(3, self._rdf_tab.set_document(document))
        if document is None:
            self._tabs.setCurrentIndex(0)

    def _apply_no_document_state(self):
        """Установка текста по умолчанию при отсутствии документа."""
        self.set_document(None)

    def _on_validation_result_changed(self, document: Document):
        self.validation_result_changed.emit(document)
