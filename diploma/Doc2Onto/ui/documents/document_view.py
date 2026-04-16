from html import escape
from pathlib import Path
from typing import Callable, Dict, Optional

import mammoth
from docx import Document as DocxDocument
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.document import Document
from modules.extractor import ExtractionResult
from modules.validator import ValidationResult


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

        # --- Поля ---
        self._terms_empty_label = QLabel("")
        self._terms_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._terms_list_widget = QWidget()
        self._terms_list_layout = QVBoxLayout(self._terms_list_widget)
        self._terms_list_layout.setContentsMargins(0, 0, 0, 0)
        self._terms_list_layout.setSpacing(6)
        self._terms_list_layout.addStretch()

        self._terms_scroll = QScrollArea()
        self._terms_scroll.setWidgetResizable(True)
        self._terms_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._terms_scroll.setWidget(self._terms_list_widget)

        self._terms_page = QWidget()
        terms_page_layout = QVBoxLayout(self._terms_page)
        terms_page_layout.setContentsMargins(0, 0, 0, 0)
        terms_page_layout.setSpacing(0)
        terms_page_layout.addWidget(self._terms_empty_label)
        terms_page_layout.addWidget(self._terms_scroll, 1)

        self._tabs.addTab(_wrap_tab_page_content(self._terms_page), "Поля")
        self._terms_rows: Dict[str, _FieldRowWidget] = {}
        self._extracted_values: Dict[str, str] = {}

        # --- RDF ---
        self._rdf_label = QLabel("")
        self._rdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(_wrap_tab_page_content(self._rdf_label), "RDF")

        # Установка текста по умолчанию при отсутствии документа
        self._apply_no_document_state()

    def set_document(self, document: Optional[Document]):
        """Установка документа в виджет."""
        self._document = document
        if document is None:
            self._apply_no_document_state()
            return

        self._refresh_original()
        self._refresh_uddm()
        self._refresh_terms()
        self._set_rdf_placeholder()

    def _apply_no_document_state(self):
        """Установка текста по умолчанию при отсутствии документа."""
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

        self._terms_empty_label.setText("Поля недоступны")
        self._terms_empty_label.setVisible(True)
        self._terms_scroll.setVisible(False)
        self._clear_terms_rows()
        self._tabs.setTabEnabled(2, False)

        self._tabs.setTabEnabled(3, False)

        self._tabs.setCurrentIndex(0)

    def _original_path(self) -> Optional[Path]:
        if self._document is None:
            return None
        return self._document.original_file_path()

    def _open_original_in_word(self):
        path = self._original_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _refresh_original(self):
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

    def _refresh_uddm(self):
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

    def _set_rdf_placeholder(self):
        self._rdf_label.setText("Пока не поддерживается")

    def _clear_terms_rows(self):
        while self._terms_list_layout.count():
            item = self._terms_list_layout.takeAt(0)
            child_widget = item.widget()
            if child_widget is not None:
                child_widget.deleteLater()
        self._terms_list_layout.addStretch()
        self._terms_rows = {}

    def _refresh_terms(self):
        doc = self._document
        self._clear_terms_rows()
        self._tabs.setTabEnabled(2, True)
        self._terms_empty_label.setVisible(True)
        self._terms_scroll.setVisible(False)
        self._extracted_values = {}

        if doc is None or doc.template is None:
            self._terms_empty_label.setText("Поля недоступны")
            return

        extraction_path = doc.extraction_result_file_path()
        if not extraction_path.exists():
            self._terms_empty_label.setText("Результаты экстракции пока отсутствуют")
            return

        try:
            extraction = ExtractionResult.load(extraction_path)
        except Exception as exc:
            self._terms_empty_label.setText(f"Не удалось прочитать результаты экстракции: {exc}")
            return

        validation = ValidationResult()
        validation_path = doc.validation_result_file_path()
        if validation_path.exists():
            try:
                validation = ValidationResult.load(validation_path)
            except Exception:
                validation = ValidationResult()

        if not doc.template.fields:
            if doc.template.code:
                doc.template.fields = doc.template.code.fields()
            else:
                self._terms_empty_label.setText("Шаблон документа не содержит кода")
                return

        self._terms_empty_label.setVisible(False)
        self._terms_scroll.setVisible(True)
        # self._tabs.setTabEnabled(2, True)

        for field in doc.template.fields:
            extraction_data = extraction.fields.get(field.name, {})
            validation_data = validation.fields.get(field.name, {})
            extracted_value = extraction_data.get("value") or ""
            self._extracted_values[field.name] = extracted_value

            corrected_value = validation_data.get("corrected_value")
            displayed_value = corrected_value if isinstance(corrected_value, str) else extracted_value
            is_valid = bool(validation_data.get("valid", False))
            error_text = validation_data.get("error") or extraction_data.get("error")
            extraction_source = extraction_data.get("source")
            correction_source = validation_data.get("source")

            row = _FieldRowWidget(
                name=field.name,
                description=field.description,
                value=displayed_value,
                is_valid=is_valid,
                error_text=error_text,
                extraction_source=extraction_source if isinstance(extraction_source, str) else None,
                correction_source=correction_source if isinstance(correction_source, str) else None,
                on_change=self._handle_term_row_change,
            )
            self._terms_rows[field.name] = row
            self._terms_list_layout.insertWidget(self._terms_list_layout.count() - 1, row)

    def _handle_term_row_change(self, field_name: str, value: str, is_valid: bool):
        doc = self._document
        if doc is None:
            return

        validation_path = doc.validation_result_file_path()
        if validation_path.exists():
            try:
                validation = ValidationResult.load(validation_path)
            except Exception:
                validation = ValidationResult()
        else:
            validation = ValidationResult()

        base_value = self._extracted_values.get(field_name, "")
        normalized_value = value.strip()

        if is_valid:
            if normalized_value and normalized_value != base_value:
                validation.set_corrected(field_name, normalized_value, "human")
            else:
                validation.set_valid(field_name)
        else:
            row = self._terms_rows.get(field_name)
            manual_error = None
            if row is not None:
                manual_error = row.error_text()
            validation.set_invalid(field_name, manual_error or "Поле отмечено пользователем как невалидное")

        try:
            validation.save(validation_path)
        except OSError:
            pass


class _FieldRowWidget(QFrame):
    """Одна строка поля: имя, описание, значение, валидность, ошибка, источники."""

    def __init__(
        self,
        name: str,
        description: Optional[str],
        value: str,
        is_valid: bool,
        error_text: Optional[str],
        extraction_source: Optional[str],
        correction_source: Optional[str],
        on_change: Callable[[str, str, bool], None],
    ):
        super().__init__()
        self._name = name
        self._on_change = on_change
        self._is_updating = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #3a3a3a; border-radius: 6px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setStyleSheet("QLabel { font-weight: 600; }")
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        self._valid_checkbox = QCheckBox("Валидно")
        self._valid_checkbox.setChecked(is_valid)
        header_layout.addWidget(self._valid_checkbox)

        layout.addLayout(header_layout)

        if description:
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("QLabel { color: #9a9a9a; }")
            layout.addWidget(description_label)

        self._value_edit = QLineEdit()
        self._value_edit.setText(value)
        self._value_edit.setPlaceholderText("Значение поля")
        layout.addWidget(self._value_edit)

        sources_text = self._build_sources_text(extraction_source, correction_source)
        self._sources_label = QLabel(sources_text)
        self._sources_label.setVisible(bool(sources_text))
        self._sources_label.setStyleSheet("QLabel { color: #8a8a8a; }")
        layout.addWidget(self._sources_label)

        self._error_label = QLabel(error_text or "")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("QLabel { color: #ff8a80; }")
        layout.addWidget(self._error_label)

        self._valid_checkbox.toggled.connect(self._emit_change)
        self._value_edit.textChanged.connect(self._emit_change)
        self._update_error_visibility()

    def _build_sources_text(self, extraction_source: Optional[str], correction_source: Optional[str]) -> str:
        markers = []
        if extraction_source == "template":
            markers.append("извлечено: шаблон")
        elif extraction_source == "llm":
            markers.append("извлечено: LLM")

        if correction_source == "llm":
            markers.append("исправлено: LLM")
        elif correction_source == "human":
            markers.append("исправлено: вручную")

        return " | ".join(markers)

    def _emit_change(self):
        if self._is_updating:
            return
        self._update_error_visibility()
        self._on_change(self._name, self._value_edit.text(), self._valid_checkbox.isChecked())

    def _update_error_visibility(self):
        show_error = (not self._valid_checkbox.isChecked()) and bool(self._error_label.text().strip())
        self._error_label.setVisible(show_error)

    def error_text(self) -> Optional[str]:
        text = self._error_label.text().strip()
        return text or None
