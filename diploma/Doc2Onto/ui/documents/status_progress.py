from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from core.document import Document


class StatusProgressWidget(QWidget):
    """Виджет для отображения прогресса обработки документа по статусу."""

    steps = [
        "Документ загружен",
        "Извлечены данные (UDDM)",
        "Определён класс документа",
        "Извлечены термы",
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
            # label.setMinimumWidth(80)

            main_layout.addWidget(label, 1)
            self.step_labels.append(label)

    def set_status(self, status: Document.Status):
        index = int(status) + 1

        for i, label in enumerate(self.step_labels, start=1):
            if i <= index:
                label.setStyleSheet("color: green;font-weight:bold")
            else:
                label.setStyleSheet("color: gray")
