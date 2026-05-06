from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from models.document import Document
from ui.common.design import UI_COLOR_GREEN, UI_COLOR_RED


class StatusBarWidget(QWidget):
    """Прогресс обработки документа по статусам и сообщение об ошибке пайплайна."""

    _STEPS = [
        "Документ загружен",
        "Извлечены данные",
        "Определён класс",
        "Извлечены поля",
        "Пройдена валидация",
        "Построены триплеты",
        "Знания добавлены",
    ]

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        steps_row = QHBoxLayout()
        steps_row.setContentsMargins(0, 0, 0, 0)
        steps_row.setSpacing(0)

        self._step_labels: list[QLabel] = []
        for text in self._STEPS:
            label = QLabel(f"●\n{text}")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            steps_row.addWidget(label, 1)
            self._step_labels.append(label)

        root.addLayout(steps_row)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(f"color: {UI_COLOR_RED};")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._error_label)

    def set_status(self, document: Optional[Document]):
        """Отображает текущий статус документа и последнюю ошибку пайплайна (если есть)."""
        if document is None:
            for label in self._step_labels:
                label.setStyleSheet("color: gray")
            self._error_label.setText("")
            return

        status = document.status
        failed_target = document.pipeline_failed_target
        error_message = document.pipeline_error_message

        status_idx = int(status)
        failed_idx: Optional[int] = int(failed_target) if failed_target is not None else None

        for i, label in enumerate(self._step_labels):
            if failed_idx is not None and i == failed_idx:
                label.setStyleSheet(f"color: {UI_COLOR_RED}; font-weight: bold")
            elif i <= status_idx:
                label.setStyleSheet(f"color: {UI_COLOR_GREEN}; font-weight: bold")
            else:
                label.setStyleSheet("color: gray")

        if error_message:
            self._error_label.setText(error_message)
        else:
            self._error_label.setText("")
