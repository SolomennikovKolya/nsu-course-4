from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from pathlib import Path
from typing import Optional, List

from app.context import get_pipeline, get_doc_manager
from app.pipeline import PipelineResult
from app.settings import APP_NAME
from core.document import Document
from modules.converter.registry import ConverterRegistry
from ui.documents.document_info import DocumentInfoWidget


class DocumentsTab(QWidget):
    """Интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()

        self.pipeline = get_pipeline()
        self.doc_manager = get_doc_manager()
        self.documents_cache: List[Document] = []

        # --- Список документов ---
        self.upload_btn = QPushButton("Загрузить документ")
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)

        left_widget = QWidget()
        left_widget.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self.upload_btn)
        left_layout.addWidget(self.tree)

        # --- Информация о документе ---
        self.info_widget = DocumentInfoWidget()

        # --- Основной макет ---
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(self.info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # --- Сигналы ---
        self.upload_btn.clicked.connect(self.add_document)
        self.tree.itemSelectionChanged.connect(self.update_info)
        self.info_widget.document_changed.connect(self.refresh_documents_tree)
        self.info_widget.document_deleted.connect(self.on_document_deleted)

        self.refresh_documents_tree()

    def add_document(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Выберите документы")
        if not file_paths:
            return

        added_any = False

        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            file_name = file_path.name

            if not ConverterRegistry.is_format_supported(file_path.suffix.lower().replace(".", "")):
                QMessageBox.critical(self, APP_NAME, f'Формат документа "{file_name}" не поддерживается.')
                continue

            # if self.doc_manager.is_file_exists(file_path):
            #     QMessageBox.warning(self, APP_NAME, f'Документ "{file_name}" уже существует в системе.')
            #     continue

            doc = self.doc_manager.add(file_path)

            # Пытаемся извлечь UDDM сразу после загрузки
            res = self.pipeline.run(doc, final_stage=Document.Status.UDDM_EXTRACTED)
            if res == PipelineResult.FAILED:
                self.doc_manager.delete(doc)
                QMessageBox.critical(self, APP_NAME, f'Не удалось извлечь данные из документа "{file_name}".')
                continue

            self.doc_manager.save_metadata(doc)
            added_any = True

        if added_any:
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
        self.documents_cache = self.doc_manager.list()

        groups: dict[str, list[Document]] = {}
        for doc in self.documents_cache:
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

                if doc.status == Document.Status.UPLOADED or doc.status == Document.Status.UDDM_EXTRACTED:
                    color = QColor("white")
                elif doc.status == Document.Status.ADDED_TO_MODEL:
                    color = QColor("#4CAF50")
                else:
                    color = QColor("#FFC107")

                item.setForeground(0, color)
                folder.addChild(item)

        self.tree.expandAll()

    def refresh_templates(self):
        self.refresh_documents_tree()
        self.info_widget.refresh_classes()
