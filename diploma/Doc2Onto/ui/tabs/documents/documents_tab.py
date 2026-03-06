from infrastructure.document_repository import DocumentRepository
from app.pipeline_engine import PipelineEngine
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QHBoxLayout
)
from PySide6.QtCore import Qt


class DocumentsTab(QWidget):
    """Главный интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()

        self.pipeline = PipelineEngine()      # Движок обработки документов
        self.main_layout = QHBoxLayout(self)  # Основной горизонтальный макет для разделения на две панели

        # Левая панель
        left_layout = QVBoxLayout()
        self.upload_btn = QPushButton("Загрузить документ")  # Кнопка для загрузки документа
        self.list_widget = QListWidget()                     # Список для отображения загруженных документов
        left_layout.addWidget(self.upload_btn)
        left_layout.addWidget(self.list_widget)
        self.main_layout.addLayout(left_layout, 1)

        # Правая панель
        right_layout = QVBoxLayout()
        self.info_label = QLabel("Выберите документ")          # Метка для отображения информации о выбранном документе
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.process_btn = QPushButton("Запустить обработку")  # Кнопка для запуска pipeline обработки документа
        right_layout.addWidget(self.info_label)
        right_layout.addWidget(self.process_btn)
        self.main_layout.addLayout(right_layout, 2)

        # Назначения кнопок
        self.upload_btn.clicked.connect(self.upload_document)
        self.process_btn.clicked.connect(self.process_document)
        self.list_widget.itemSelectionChanged.connect(self.update_info)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        self.documents = DocumentRepository.list_documents()
        for doc in self.documents:
            self.list_widget.addItem(doc.name)

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите документ")
        if file_path:
            DocumentRepository.save(file_path)
            self.refresh_list()

    def get_selected_document(self):
        selected = self.list_widget.currentRow()
        if selected >= 0:
            return self.documents[selected]
        return None

    def update_info(self):
        doc = self.get_selected_document()
        if doc:
            self.info_label.setText(f"Имя: {doc.name}\nСтатус: {doc.status}")
        else:
            self.info_label.setText("Выберите документ")

    def process_document(self):
        doc = self.get_selected_document()
        if doc:
            doc = self.pipeline.run(doc)
            self.update_info()
