from html import escape
from pathlib import Path
from typing import Optional

import mammoth
from docx import Document as DocxDocument
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.document import Document


def _wrap_tab_page_content(inner: QWidget) -> QWidget:
    """Вкладывает виджет страницы вкладки в layout с отступами."""
    outer = QWidget()
    layout = QVBoxLayout(outer)
    layout.setContentsMargins(4, 8, 4, 8)
    layout.setSpacing(0)
    layout.addWidget(inner)
    return outer


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _docx_to_html_fragment(path: Path) -> str:
    """DOCX → HTML (сохраняет типичную разметку Word; не идентичен Word построчно)."""
    with path.open("rb") as f:
        result = mammoth.convert_to_html(f)
    return result.value


def _wrap_original_html(body_fragment: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{
    font-family: "Segoe UI", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    color: #ffffff;
  }}
  body, p, li, td, th, div, span, strong, em {{ color: #ffffff; }}
  a {{ color: #a8d4ff; }}
  table {{ border-collapse: collapse; margin: 0.5em 0; }}
  td, th {{ border: 1px solid #888888; padding: 4px 6px; vertical-align: top; }}
  p {{ margin: 0.25em 0; }}
</style>
</head>
<body>{body_fragment}</body>
</html>"""


class DocumentViewWidget(QWidget):
    """Вкладки предпросмотра: оригинал, UDDM, термы и RDF."""

    def __init__(self):
        super().__init__()

        self._document: Optional[Document] = None
        self._tabs = QTabWidget()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tabs)

        # --- Оригинал ---
        self._original_docx_bar = QWidget()
        docx_bar_layout = QVBoxLayout(self._original_docx_bar)
        docx_bar_layout.setContentsMargins(0, 0, 0, 8)
        self._original_disclaimer = QLabel(" Предпросмотр документа может отличаться от реального вида документа")
        self._original_disclaimer.setWordWrap(True)
        self._original_disclaimer.setStyleSheet("QLabel { color: #8a8a8a; }")
        self._original_open_word_btn = QPushButton("Посмотреть в Word")
        self._original_open_word_btn.clicked.connect(self._open_original_in_word)
        docx_bar_layout.addWidget(self._original_disclaimer)
        docx_bar_layout.addWidget(self._original_open_word_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._original_view = QTextBrowser()
        self._original_view.setReadOnly(True)
        self._original_view.setOpenExternalLinks(True)
        self._original_view.setFrameShape(QFrame.Shape.NoFrame)

        self._original_page = QWidget()
        original_page_layout = QVBoxLayout(self._original_page)
        original_page_layout.setContentsMargins(0, 0, 0, 0)
        original_page_layout.setSpacing(0)
        original_page_layout.addWidget(self._original_docx_bar)
        original_page_layout.addWidget(self._original_view, 1)
        self._original_docx_bar.setVisible(False)

        self._tabs.addTab(_wrap_tab_page_content(self._original_page), "Оригинал")

        # --- UDDM ---
        self._uddm_tabs = QTabWidget()
        self._uddm_plain = QTextEdit()
        self._uddm_plain.setReadOnly(True)
        self._uddm_plain.setPlaceholderText("Сплошной текст документа отсутствует")
        self._uddm_plain.setFrameShape(QFrame.Shape.NoFrame)
        self._uddm_tabs.addTab(_wrap_tab_page_content(self._uddm_plain), "Сплошной текст")

        self._uddm_html = QTextBrowser()
        self._uddm_html.setOpenExternalLinks(True)
        self._uddm_html.setFrameShape(QFrame.Shape.NoFrame)
        self._uddm_tabs.addTab(_wrap_tab_page_content(self._uddm_html), "HTML представление")

        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")

        self._uddm_tree = QTextEdit()
        self._uddm_tree.setReadOnly(True)
        self._uddm_tree.setFont(mono)
        self._uddm_tree.setPlaceholderText("Дерево документа отсутствует")
        self._uddm_tree.setFrameShape(QFrame.Shape.NoFrame)
        self._uddm_tabs.addTab(_wrap_tab_page_content(self._uddm_tree), "Дерево")

        uddm_holder = QWidget()
        uddm_holder_layout = QVBoxLayout(uddm_holder)
        uddm_holder_layout.setContentsMargins(2, 0, 0, 0)
        uddm_holder_layout.setSpacing(0)
        uddm_holder_layout.addWidget(self._uddm_tabs)
        self._tabs.addTab(uddm_holder, "UDDM")

        # --- Термы ---
        self._terms_label = QLabel("")
        self._terms_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(_wrap_tab_page_content(self._terms_label), "Термы")

        # --- RDF ---
        self._rdf_label = QLabel("")
        self._rdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(_wrap_tab_page_content(self._rdf_label), "RDF")

        self._apply_no_document_state()

    def set_document(self, document: Optional[Document]) -> None:
        self._document = document
        if document is None:
            self._apply_no_document_state()
            return

        self._refresh_original()
        self._refresh_uddm()
        self._set_terms_rdf_placeholders()

    def _apply_no_document_state(self) -> None:
        self._original_view.clear()
        self._original_view.setPlaceholderText("Документ не выбран")
        self._original_docx_bar.setVisible(False)
        self._tabs.setTabEnabled(0, False)
        self._uddm_plain.clear()
        self._uddm_html.clear()
        self._uddm_tree.clear()
        self._uddm_tabs.setTabEnabled(0, False)
        self._uddm_tabs.setTabEnabled(1, False)
        self._uddm_tabs.setTabEnabled(2, False)
        self._uddm_tabs.setCurrentIndex(0)
        self._tabs.setTabEnabled(1, False)
        self._tabs.setTabEnabled(2, False)
        self._tabs.setTabEnabled(3, False)
        self._tabs.setCurrentIndex(0)

    def _original_path(self) -> Optional[Path]:
        if self._document is None:
            return None
        return self._document.original_file_path()

    def _open_original_in_word(self) -> None:
        path = self._original_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _refresh_original(self) -> None:
        path = self._original_path()
        self._original_view.clear()
        self._original_view.setPlaceholderText("")
        self._original_docx_bar.setVisible(False)

        if path is None or not path.exists():
            self._original_view.setPlaceholderText("Оригинальный файл документа отсутствует")
            self._tabs.setTabEnabled(0, False)
            return

        self._tabs.setTabEnabled(0, True)
        ext = path.suffix.lower()

        if ext == ".docx":
            try:
                fragment = _docx_to_html_fragment(path)
                self._original_view.setHtml(_wrap_original_html(fragment))
            except Exception as exc:
                try:
                    docx = DocxDocument(str(path))
                    lines = [p.text for p in docx.paragraphs]
                    plain = "\n".join(lines)
                    note = (
                        "Не удалось показать форматированный предпросмотр "
                        f"({exc}). Ниже — только текст параграфов.\n\n"
                    )
                    self._original_view.setPlainText(note + plain)
                except Exception as exc2:
                    self._original_view.setHtml(
                        "<p style='color:#ff8a80;'>Не удалось открыть DOCX.</p>"
                        f"<pre style='color:#eeeeee;'>{escape(str(exc2))}</pre>"
                    )
        elif ext == ".doc":
            self._original_view.setPlainText(
                "Предпросмотр файлов формата .doc (Word 97–2003) не поддерживается.\n"
                "Откройте документ во внешнем приложении или сохраните копию в .docx."
            )
        else:
            self._original_view.setPlainText(
                f"Предпросмотр для формата «{ext or '(нет расширения)'}» не поддерживается."
            )

        if path.exists() and path.suffix.lower() == ".docx":
            self._original_docx_bar.setVisible(True)
            self._original_open_word_btn.setEnabled(True)

    def _refresh_uddm(self) -> None:
        doc = self._document
        if doc is None:
            return

        plain_path = doc.plain_text_file_path()
        html_path = doc.uddm_html_view_file_path()
        tree_path = doc.uddm_tree_view_file_path()

        self._uddm_plain.clear()
        self._uddm_html.clear()
        self._uddm_tree.clear()

        uddm_any = False

        if plain_path.exists():
            self._uddm_tabs.setTabEnabled(0, True)
            uddm_any = True
            try:
                self._uddm_plain.setPlainText(_read_text_file(plain_path))
            except OSError as exc:
                self._uddm_plain.setPlainText(f"Не удалось прочитать файл: {exc}")
        else:
            self._uddm_plain.setPlaceholderText("Сплошной текст документа отсутствует")
            self._uddm_tabs.setTabEnabled(0, False)

        if html_path.exists():
            self._uddm_tabs.setTabEnabled(1, True)
            uddm_any = True
            url = QUrl.fromLocalFile(str(html_path.resolve()))
            self._uddm_html.setSource(url)
        else:
            self._uddm_html.setHtml(
                "<p style='color:gray;'>HTML представление документа отсутствует</p>"
            )
            self._uddm_tabs.setTabEnabled(1, False)

        if tree_path.exists():
            self._uddm_tabs.setTabEnabled(2, True)
            uddm_any = True
            try:
                self._uddm_tree.setPlainText(_read_text_file(tree_path))
            except OSError as exc:
                self._uddm_tree.setPlainText(f"Не удалось прочитать файл: {exc}")
        else:
            self._uddm_tree.setPlaceholderText("Дерево документа отсутствует")
            self._uddm_tabs.setTabEnabled(2, False)

        self._tabs.setTabEnabled(1, uddm_any)

    def _set_terms_rdf_placeholders(self) -> None:
        self._terms_label.setText("Пока не поддерживается")
        self._rdf_label.setText("Пока не поддерживается")
