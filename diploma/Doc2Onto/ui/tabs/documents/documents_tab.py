from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QHBoxLayout
)
from PySide6.QtCore import Qt
from pathlib import Path
from typing import Optional

from core.document.document import Document
from infrastructure.storage.document_manager import DocumentManager
from app.pipeline_engine import PipelineEngine


class DocumentsTab(QWidget):
    """Главный интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()

        self.pipeline = PipelineEngine()           # Движок обработки документов
        self.document_manager = DocumentManager()  # Менеджер для хранения и управления документами
        self.documents = []                        # Локальный кэш списка документов
        self.main_layout = QHBoxLayout(self)       # Основной горизонтальный макет для разделения на две панели

        # Список документов
        left_layout = QVBoxLayout()
        self.upload_btn = QPushButton("Загрузить документ")
        self.list_widget = QListWidget()
        left_layout.addWidget(self.upload_btn)
        left_layout.addWidget(self.list_widget)
        self.main_layout.addLayout(left_layout, 1)

        # Панель информации
        right_layout = QVBoxLayout()
        self.info_label = QLabel("Выберите документ")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.process_btn = QPushButton("Запустить обработку")
        right_layout.addWidget(self.info_label)
        right_layout.addWidget(self.process_btn)
        self.main_layout.addLayout(right_layout, 2)

        # Сигналы
        self.upload_btn.clicked.connect(self.add_document)
        self.process_btn.clicked.connect(self.process_document)
        self.list_widget.itemSelectionChanged.connect(self.update_info)

        self.refresh_documents_list()

    def refresh_documents_list(self):
        """Обновляет список документов."""
        self.list_widget.clear()
        self.documents = self.document_manager.list()
        for doc in self.documents:
            self.list_widget.addItem(doc.name)

    def add_document(self):
        """Добавление документа в систему."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите документ")
        if file_path:
            self.document_manager.add(Path(file_path))
            self.refresh_documents_list()

    def get_selected_document(self) -> Optional[Document]:
        selected = self.list_widget.currentRow()
        return self.documents[selected] if 0 <= selected < len(self.documents) else None

    def update_info(self):
        """Обновление информации о выбранном документе."""
        doc = self.get_selected_document()
        if doc:
            self.info_label.setText(f"Имя: {doc.name}\nСтатус: {doc.status}")
        else:
            self.info_label.setText("Выберите документ")

    def process_document(self):
        """Запуск pipeline обработки."""
        doc = self.get_selected_document()
        if doc:
            doc = self.pipeline.run(doc)
            self.document_manager.save_metadata(doc)
            self.update_info()
