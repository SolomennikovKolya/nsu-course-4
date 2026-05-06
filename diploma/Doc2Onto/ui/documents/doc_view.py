from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from models.document import Document
from ui.documents.view.common import wrap_tab_page_content
from ui.documents.view.original_tab import DocumentViewOriginalTab
from ui.documents.view.uddm_tab import DocumentViewUddmTab
from ui.documents.view.graph_tab import DocumentViewGraphTab


class DocumentViewWidget(QWidget):
    """Вкладки предпросмотра документа и его промежуточных данных."""

    def __init__(self):
        super().__init__()

        self._document: Optional[Document] = None
        self._tabs = QTabWidget()
        self._original_tab = DocumentViewOriginalTab()
        self._uddm_tab = DocumentViewUddmTab()
        self._graph_tab = DocumentViewGraphTab()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tabs)

        self._tabs.addTab(wrap_tab_page_content(self._original_tab), "Оригинал")
        self._tabs.addTab(self._uddm_tab, "UDDM")
        self._tabs.addTab(wrap_tab_page_content(self._graph_tab), "Граф")
        self._apply_no_document_state()

    def set_document(self, document: Optional[Document]):
        """Установка текущего документа в виджет."""
        self._document = document
        self._tabs.setTabEnabled(0, self._original_tab.set_document(document))
        self._tabs.setTabEnabled(1, self._uddm_tab.set_document(document))
        self._tabs.setTabEnabled(2, self._graph_tab.set_document(document))
        if document is None:
            self._tabs.setCurrentIndex(0)

    def _apply_no_document_state(self):
        """Установка текста по умолчанию при отсутствии документа."""
        self.set_document(None)
