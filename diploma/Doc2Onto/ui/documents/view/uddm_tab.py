from typing import Optional
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget

from models.document import Document
from ui.documents.view.common import read_text_file, wrap_tab_page_content


class DocumentViewUddmTab(QWidget):
    """Вкладка для отображения UDDM документа в различных форматах."""

    def __init__(self):
        super().__init__()

        self._tabs = QTabWidget()
        self._document: Optional[Document] = None

        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")

        self._tree = QTextEdit()
        self._tree.setReadOnly(True)
        self._tree.setFont(mono)
        self._tree.setPlaceholderText("Дерево документа отсутствует")
        self._tree.setFrameShape(QFrame.Shape.NoFrame)
        self._tabs.addTab(wrap_tab_page_content(self._tree), "Дерево")

        self._html = QTextBrowser()
        self._html.setOpenExternalLinks(True)
        self._html.setFrameShape(QFrame.Shape.NoFrame)
        self._tabs.addTab(wrap_tab_page_content(self._html), "HTML представление")

        self._plain = QTextEdit()
        self._plain.setReadOnly(True)
        self._plain.setPlaceholderText("Сплошной текст документа отсутствует")
        self._plain.setFrameShape(QFrame.Shape.NoFrame)
        self._tabs.addTab(wrap_tab_page_content(self._plain), "Сплошной текст")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tabs)

    def set_document(self, document: Optional[Document]) -> bool:
        if self._document is None and document is not None:
            self._tabs.setCurrentIndex(0)
        self._document = document

        self._tree.clear()
        self._html.clear()
        self._plain.clear()

        if document is None:
            self._tabs.setTabEnabled(0, False)
            self._tabs.setTabEnabled(1, False)
            self._tabs.setTabEnabled(2, False)
            return False

        tree_path = document.uddm_tree_view_file_path()
        html_path = document.uddm_html_view_file_path()
        plain_path = document.plain_text_file_path()
        has_any = False

        if tree_path.exists():
            self._tabs.setTabEnabled(0, True)
            has_any = True
            try:
                self._tree.setPlainText(read_text_file(tree_path))
            except OSError as exc:
                self._tree.setPlainText(f"Не удалось прочитать файл: {exc}")
        else:
            self._tree.setPlaceholderText("Дерево документа отсутствует")
            self._tabs.setTabEnabled(0, False)

        if html_path.exists():
            self._tabs.setTabEnabled(1, True)
            has_any = True
            self._html.setSource(QUrl.fromLocalFile(str(html_path.resolve())))
        else:
            self._html.setHtml("<p style='color:gray;'>HTML представление документа отсутствует</p>")
            self._tabs.setTabEnabled(1, False)

        if plain_path.exists():
            self._tabs.setTabEnabled(2, True)
            has_any = True
            try:
                self._plain.setPlainText(read_text_file(plain_path))
            except OSError as exc:
                self._plain.setPlainText(f"Не удалось прочитать файл: {exc}")
        else:
            self._plain.setPlaceholderText("Сплошной текст документа отсутствует")
            self._tabs.setTabEnabled(2, False)

        return has_any
