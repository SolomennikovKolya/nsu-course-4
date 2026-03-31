from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QPushButton, QLabel,
    QInputDialog
)

from app.context import get_temp_manager


class TemplatesTab(QWidget):
    """Интерфейс для управления шаблонами."""

    def __init__(self):
        super().__init__()

        self.manager = get_temp_manager()     # Менеджер для хранения и управления шаблонами
        self.templates = []                   # Локальный кэш списка шаблонов
        self.main_layout = QHBoxLayout(self)  # Основной горизонтальный макет для разделения на две панели

        # Список шаблонов
        left_layout = QVBoxLayout()
        self.add_button = QPushButton("Добавить шаблон")
        self.list_widget = QListWidget()
        left_layout.addWidget(self.add_button)
        left_layout.addWidget(self.list_widget)

        # Панель информации
        right_layout = QVBoxLayout()
        self.info_label = QLabel("Выберите шаблон")
        right_layout.addWidget(self.info_label)
        right_layout.addStretch()

        self.main_layout.addLayout(left_layout, 1)
        self.main_layout.addLayout(right_layout, 2)

        # Сигналы
        self.add_button.clicked.connect(self.add_template)
        self.list_widget.itemSelectionChanged.connect(self.update_info)

        self.refresh_templates_list()

    def refresh_templates_list(self):
        """Обновление списка шаблонов."""
        self.list_widget.clear()
        self.templates = self.manager.list()
        for t in self.templates:
            self.list_widget.addItem(t.name)

    def add_template(self):
        """Создание нового шаблона."""
        name, ok = QInputDialog.getText(
            self,
            "Добавить шаблон",
            "Название шаблона:"
        )
        if not ok or not name:
            return

        self.manager.add(name)
        self.refresh_templates_list()

    def get_selected_template(self):
        selected = self.list_widget.currentRow()
        return self.templates[selected] if 0 <= selected < len(self.templates) else None

    def update_info(self):
        """Обновление информации о выбранном шаблоне."""
        temp = self.get_selected_template()
        if temp:
            self.info_label.setText(f"Название: {temp.name}")
        else:
            self.info_label.setText("Выберите шаблон")
