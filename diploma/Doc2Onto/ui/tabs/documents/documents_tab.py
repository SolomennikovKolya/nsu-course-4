from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from pathlib import Path
from typing import Optional

from core.document.document import Document
from infrastructure.storage.document_manager import DocumentManager
from infrastructure.storage.templates_manager import TemplatesManager
from app.pipeline_engine import PipelineEngine
from ui.tabs.documents.document_info_widget import DocumentInfoWidget


class DocumentsTab(QWidget):
    """Интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()

        self.pipeline = PipelineEngine()
        self.document_manager = DocumentManager()
        self.templates_manager = TemplatesManager()

        self.documents = []

        # Левая панель
        left_widget = QWidget()
        left_widget.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_widget)

        self.upload_btn = QPushButton("Загрузить документ")

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)

        left_layout.addWidget(self.upload_btn)
        left_layout.addWidget(self.tree)

        # Правая панель
        self.info_widget = DocumentInfoWidget(
            self.templates_manager,
            self.document_manager,
            self.pipeline
        )

        # Основной макет
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(self.info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # Сигналы
        self.upload_btn.clicked.connect(self.add_document)
        self.tree.itemSelectionChanged.connect(self.update_info)
        self.info_widget.documents_tree_changed.connect(self.refresh_documents_tree)
        self.info_widget.document_deleted.connect(self.on_document_deleted)

        self.refresh_documents_tree()

    def add_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите документ")
        if file_path:
            self.document_manager.add(Path(file_path))
            self.refresh_documents_tree()

    def on_document_deleted(self):
        self.refresh_documents_tree()
        self.info_widget.set_document(None)

    def get_selected_document(self) -> Optional[Document]:
        item = self.tree.currentItem()
        if not item:
            return None

        doc = item.data(0, Qt.ItemDataRole.UserRole)
        return doc

    def update_info(self):
        doc = self.get_selected_document()
        self.info_widget.set_document(doc)

    def refresh_documents_tree(self):
        self.tree.clear()
        self.documents = self.document_manager.list()

        groups: dict[str, list[Document]] = {}
        for doc in self.documents:
            key = doc.doc_class if doc.doc_class else "Без класса"
            if key not in groups:
                groups[key] = []
            groups[key].append(doc)

        ordered_keys = []
        if "Без класса" in groups:
            ordered_keys.append("Без класса")
        ordered_keys += sorted(k for k in groups.keys() if k != "Без класса")

        for group in ordered_keys:
            folder = QTreeWidgetItem([group])
            folder.setFlags(folder.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            self.tree.addTopLevelItem(folder)

            for doc in groups[group]:
                item = QTreeWidgetItem([doc.name])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)

                if doc.status.name == "UPLOADED":
                    color = QColor("white")
                elif doc.status.name == "ADDED_TO_MODEL":
                    color = QColor("#4CAF50")
                else:
                    color = QColor("#FFC107")

                item.setForeground(0, color)
                folder.addChild(item)

        self.tree.expandAll()

    def refresh_templates(self):
        self.info_widget.refresh_classes()
