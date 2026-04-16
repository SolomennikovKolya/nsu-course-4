from html import escape
from typing import Callable, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QScrollArea, QStackedLayout, QVBoxLayout, QWidget
)

from core.document import Document
from modules.extractor import ExtractionResult, FieldExtractionData
from modules.validator import ValidationResult, FieldValidationData


class DocumentViewFieldsTab(QWidget):
    """Вкладка для отображения извлечённых и валидированных полей документа с возможностью их корректировки."""

    def __init__(self):
        super().__init__()
        self._document: Optional[Document] = None
        self._rows: Dict[str, FieldRowWidget] = {}
        self._build_tab()

    def _build_tab(self):
        """Инициализация элементов вкладки."""
        self._empty_label = QLabel("")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setWidget(self._list_widget)
        self._scroll.viewport().setStyleSheet("background: transparent;")

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setSpacing(0)
        self._stack.addWidget(self._empty_label)
        self._stack.addWidget(self._scroll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._stack)

    def set_document(self, document: Optional[Document]) -> bool:
        """Установка документа во вкладку."""
        self._document = document
        self._clear_rows()

        if document is None or document.template is None:
            self._show_empty("Выберите класс документа и запустите обработку.")
            return True

        extraction_path = document.extraction_result_file_path()
        if not extraction_path.exists():
            self._show_empty("Результаты экстракции пока отсутствуют.")
            return True
        try:
            extraction_res = ExtractionResult.load(extraction_path)
        except Exception as exc:
            self._show_empty(f"Не удалось прочитать результаты экстракции: {exc}")
            return True

        validation_path = document.validation_result_file_path()
        if not validation_path.exists():
            self._show_empty("Результаты валидации пока отсутствуют.")
            return True
        try:
            validation_res = ValidationResult.load(validation_path)
        except Exception as exc:
            self._show_empty(f"Не удалось прочитать результаты валидации: {exc}")
            return True

        fields = document.template.get_fields()
        if not fields:
            self._show_empty("Не удалось загрузить поля из шаблона.")
            return True

        field_names_template = {field.name for field in fields}
        field_names_extraction = set(extraction_res.fields.keys())
        field_names_validation = set(validation_res.fields.keys())

        if field_names_template != field_names_extraction:
            self._show_empty(
                f"Неконсистентность структур: поля шаблона не совпадают с результатами экстракции. "
                f"В шаблоне: {sorted(field_names_template)}, в экстракции: {sorted(field_names_extraction)}. "
                f"Перезапустите обработку."
            )
            return True

        if field_names_template != field_names_validation:
            self._show_empty(
                f"Неконсистентность структур: поля шаблона не совпадают с результатами валидации. "
                f"В шаблоне: {sorted(field_names_template)}, в валидации: {sorted(field_names_validation)}. "
                f"Перезапустите обработку."
            )
            return True

        for field in fields:
            extraction_data = extraction_res.fields.get(field.name)
            validation_data = validation_res.fields.get(field.name)

            row = FieldRowWidget(
                parent=self._list_widget,
                field_name=field.name,
                field_description=field.description,
                extraction_data=extraction_data,
                validation_data=validation_data,
                on_change=self._handle_row_change,
            )

            self._rows[field.name] = row
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

        if self._rows:
            self._stack.setCurrentWidget(self._scroll)
        else:
            self._show_empty("Поля отсутствуют.")
        return True

    def _show_empty(self, message: str):
        """
        Отображение пустой метки с сообщением вместо всего содержимого вкладки.
        Нужно для того, чтобы не было пустого пространства в случае, если нет полей.
        """
        self._empty_label.setText("Поля недоступны. " + message)
        self._stack.setCurrentWidget(self._empty_label)

    def _clear_rows(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            else:
                del item
        self._rows = {}
        self._list_layout.addStretch()

    def _handle_row_change(self, field_name: str, new_value: str, new_valid: bool):
        """Обработка изменения значения или флага валидности поля."""
        document = self._document
        if document is None:
            return

        validation_path = document.validation_result_file_path()
        if not validation_path.exists():
            return
        try:
            validation_res = ValidationResult.load(validation_path)
        except Exception:
            return

        if new_valid:
            validation_res.set_valid_manual(field_name)
            if new_value and new_value != validation_res.get_extracted_value(field_name):
                validation_res.set_corrected_value_manual(field_name, new_value)
            else:
                validation_res.set_corrected_value_manual(field_name, None)
        else:
            validation_res.set_invalid_manual(field_name)

        try:
            validation_res.save(validation_path)
        except OSError:
            pass


class FieldRowWidget(QFrame):
    """Одна строка поля: заголовок, значение, поясняющая строка состояния."""

    _COLOR_GREEN = "#66bb6a"
    _COLOR_YELLOW = "#ffca28"
    _COLOR_GRAY = "#9e9e9e"
    _COLOR_RED = "#ef5350"

    def __init__(
        self,
        parent: QWidget,
        field_name: str,
        field_description: str,
        extraction_data: FieldExtractionData,
        validation_data: FieldValidationData,
        on_change: Callable[[str, str, bool], None],
    ):
        super().__init__(parent)
        self.setObjectName("FieldRowWidget")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._name = field_name
        self._on_change = on_change
        self._is_updating = False

        # --- Extraction (FieldExtractionData) ---
        self._value_llm = extraction_data.get("value_llm") or ""
        self._value_temp = extraction_data.get("value_temp") or ""

        # --- Validation snapshot ---
        self._extracted_value = validation_data.get("extracted_value") or ""
        self._val_err_temp = validation_data.get("error_temp")
        self._corrected_value_llm = validation_data.get("corrected_value_llm") or ""
        self._val_err_llm = validation_data.get("error_llm")
        self._corrected_value_manual = validation_data.get("corrected_value_manual") or ""

        self._init_displayed_value = self._corrected_value_manual or self._corrected_value_llm or self._extracted_value or ""
        is_valid = validation_data.get("valid")

        self.setStyleSheet(
            """
            QFrame#FieldRowWidget {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                background-color: #242424;
            }
            QFrame#FieldRowWidget QLabel {
                border: none;
                background: transparent;
            }
            QFrame#FieldRowWidget QCheckBox {
                border: none;
                background: transparent;
                spacing: 6px;
                color: #ffffff;
            }
            QFrame#FieldRowWidget QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #bdbdbd;
                border-radius: 3px;
                background: transparent;
            }
            QFrame#FieldRowWidget QCheckBox::indicator:checked {
                background: #ffffff;
                border: 1px solid #ffffff;
            }
            QFrame#FieldRowWidget QLineEdit {
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 4px 6px;
                background: #2a2a2a;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        desc_html = escape(field_description) if field_description.strip() else ""
        if desc_html:
            title_html = (
                f'<span style="font-weight:600;">{escape(self._name)}</span>'
                f'<span style="color:{self._COLOR_GRAY};"> • {desc_html}</span>'
            )
        else:
            title_html = f'<span style="font-weight:600;">{escape(self._name)}</span>'

        self._title_label = QLabel()
        self._title_label.setTextFormat(Qt.TextFormat.RichText)
        self._title_label.setText(title_html)
        self._title_label.setWordWrap(False)
        header.addWidget(self._title_label, stretch=1)

        self._valid_checkbox = QCheckBox("Валидно")
        self._valid_checkbox.setChecked(is_valid)
        header.addWidget(self._valid_checkbox, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header)

        self._value_edit = QLineEdit()
        self._value_edit.setText(self._init_displayed_value)
        self._value_edit.setPlaceholderText("Значение поля")
        layout.addWidget(self._value_edit)

        self._info_label = QLabel()
        self._info_label.setTextFormat(Qt.TextFormat.RichText)
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        self._valid_checkbox.toggled.connect(self._emit_change)
        self._value_edit.textChanged.connect(self._emit_change)
        self._refresh_info_line()

    def _refresh_info_line(self) -> None:
        valid = self._valid_checkbox.isChecked()

        if valid:
            if self._value_edit.text().strip() != self._init_displayed_value:
                text = "Исправлено вручную"
                color = self._COLOR_GREEN
            elif self._corrected_value_llm:
                text = "Исправлено LLM"
                color = self._COLOR_YELLOW
            else:
                if self._value_llm:
                    text = "Извлечено LLM"
                    color = self._COLOR_YELLOW
                else:
                    text = "Извлечено шаблоном"
                    color = self._COLOR_GREEN
            self._info_label.setText(f'<span style="color:{color};">{escape(text)}</span>')
        else:
            parts = [p for p in (self._val_err_temp, self._val_err_llm) if p]
            msg = ". ".join(parts) if parts else "Поле отмечено как невалидное"
            self._info_label.setText(f'<span style="color:{self._COLOR_RED};">{escape(msg)}</span>')

    def _emit_change(self):
        if self._is_updating:
            return

        self._refresh_info_line()
        self._on_change(self._name, self._value_edit.text().strip(), self._valid_checkbox.isChecked())
