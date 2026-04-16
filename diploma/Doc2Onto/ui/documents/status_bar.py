from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from core.document import Document


class StatusBarWidget(QWidget):
    """Виджет для отображения прогресса обработки документа по статусу."""

    steps = [
        "Документ загружен",
        "Извлечены данные (UDDM)",
        "Определён класс документа",
        "Извлечены поля",
        "Пройдена валидация",
        "Построены триплеты",
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

            main_layout.addWidget(label, 1)
            self.step_labels.append(label)

    def set_status(self, status: Document.Status, failed_status: Optional[Document.Status] = None):
        for i, label in enumerate(self.step_labels, start=1):
            if failed_status is not None and i == int(failed_status) + 1:
                label.setStyleSheet("color: red;font-weight:bold")
            elif i <= int(status) + 1:
                label.setStyleSheet("color: green;font-weight:bold")
            else:
                label.setStyleSheet("color: gray")
