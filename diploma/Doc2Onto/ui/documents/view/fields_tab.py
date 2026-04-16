from typing import Callable, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QScrollArea, QStackedLayout, QVBoxLayout, QWidget
)

from core.document import Document
from modules.extractor import ExtractionResult
from modules.validator import ValidationResult


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
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._list_widget)

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

        has_rows = False

        for field in fields:
            extraction_data = extraction_res.fields.get(field.name)
            validation_data = validation_res.fields.get(field.name)

            row = FieldRowWidget(
                extraction_data,
                validation_data,
                field_name=field.name,
                field_description=field.description,
                on_change=self._handle_row_change,
                parent=self._list_widget,
            )

            self._rows[field.name] = row
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            has_rows = True

        if has_rows:
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

    def _handle_row_change(self, field_name: str, value: str, is_valid: bool):
        """Обработка изменения значения или флага валидности поля."""
        document = self._document
        if document is None:
            return

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
            return
        try:
            validation_res = ValidationResult.load(validation_path)
        except Exception:
            return

        row = self._rows.get(field_name)
        base_value = row.extracted_value() if row is not None else ""
        normalized_value = value.strip()

        if is_valid:
            if normalized_value and normalized_value != base_value:
                validation_res.set_corrected(field_name, normalized_value, "human")
            else:
                validation_res.set_valid(field_name)
        else:
            row = self._rows.get(field_name)
            manual_error = row.error_text() if row is not None else None
            validation_res.set_invalid(field_name, manual_error or "Поле отмечено пользователем как невалидное")

        try:
            validation_res.save(validation_path)
        except OSError:
            pass


class FieldRowWidget(QFrame):
    def __init__(
        self,
        extraction_data,
        validation_data,
        on_change: Callable[[str, str, bool], None],
        *,
        field_name: str,
        field_description: Optional[str],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        extraction_dict = extraction_data if isinstance(extraction_data, dict) else {}
        validation_dict = validation_data if isinstance(validation_data, dict) else {}

        self._name = field_name
        self._extracted_value = extraction_dict.get("value") if isinstance(extraction_dict.get("value"), str) else ""
        self._on_change = on_change
        self._is_updating = False

        description = field_description if isinstance(field_description, str) else None

        corrected_value = validation_dict.get("corrected_value")
        displayed_value = corrected_value if isinstance(corrected_value, str) else self._extracted_value
        is_valid = bool(validation_dict.get("valid", False))

        error_text = validation_dict.get("error") or extraction_dict.get("error")
        error_text = error_text if isinstance(error_text, str) else None

        extraction_source = extraction_dict.get("source")
        extraction_source = extraction_source if isinstance(extraction_source, str) else None
        correction_source = validation_dict.get("source")
        correction_source = correction_source if isinstance(correction_source, str) else None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #3a3a3a; border-radius: 6px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        name_label = QLabel(self._name)
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
        self._value_edit.setText(displayed_value)
        self._value_edit.setPlaceholderText("Значение поля")
        layout.addWidget(self._value_edit)

        sources_text = self._build_sources_text(extraction_source, correction_source)
        self._sources_label = QLabel(sources_text)
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

    def extracted_value(self) -> str:
        return self._extracted_value

    def error_text(self) -> Optional[str]:
        text = self._error_label.text().strip()
        return text or None
