from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

from core.document.status import DocumentStatus


class StatusProgressWidget(QWidget):
    """Виджет для отображения прогресса обработки документа по статусу."""

    steps = [
        "Документ загружен",
        "Извлечены данные",
        "Извлечены знания",
        "Знания валидированы",
        "Знания добавлены в модель"
    ]

    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout(self)
        self.step_labels = []

        for step in self.steps:
            label = QLabel(f"●\n{step}")
            label.setStyleSheet("color: gray")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            label.setMinimumWidth(80)

            main_layout.addWidget(label, 1)
            self.step_labels.append(label)

    def set_status(self, status: DocumentStatus):
        index = int(status)

        for i, label in enumerate(self.step_labels, start=1):
            if i <= index:
                label.setStyleSheet("color: green;font-weight:bold")
            else:
                label.setStyleSheet("color: gray")
