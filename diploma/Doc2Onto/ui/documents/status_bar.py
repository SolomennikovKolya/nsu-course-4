"""Статус-бар обработки документа: прогресс по этапам и сообщение об ошибке."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.settings import SPACING
from models.document import Document
from ui.common.qss import set_severity

_STEPS = [
    "Документ загружен",
    "Извлечены данные",
    "Определён класс",
    "Извлечены поля",
    "Построены триплеты",
    "Знания добавлены",
]


class StatusBarWidget(QWidget):
    """Прогресс обработки документа по статусам и сообщение об ошибке пайплайна."""

    def __init__(self):
        super().__init__()
        self._step_labels: list[QLabel] = []
        self._build_ui()

    def set_status(self, document: Document | None):
        """Отображает текущий статус документа и последнюю ошибку пайплайна (если есть)."""
        if document is None:
            for label in self._step_labels:
                set_severity(label, "disabled")
            self._error_label.setText("")
            return

        status_idx = int(document.status)
        failed_idx = (
            int(document.pipeline_failed_target) if document.pipeline_failed_target is not None else None
        )

        for i, label in enumerate(self._step_labels):
            if failed_idx is not None and i == failed_idx:
                set_severity(label, "error")
            elif i <= status_idx:
                set_severity(label, "success")
            else:
                set_severity(label, "disabled")

        self._error_label.setText(document.pipeline_error_message or "")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING)

        steps_row = QHBoxLayout()
        steps_row.setContentsMargins(0, 0, 0, 0)
        steps_row.setSpacing(0)

        for text in _STEPS:
            label = QLabel(f"●\n{text}")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            set_severity(label, "disabled")
            steps_row.addWidget(label, 1)
            self._step_labels.append(label)

        root.addLayout(steps_row)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        set_severity(self._error_label, "error")
        root.addWidget(self._error_label)
