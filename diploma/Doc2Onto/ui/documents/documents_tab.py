from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QHBoxLayout,
    QSplitter, QMessageBox,
)

from app.context import get_pipeline, get_doc_manager
from app.settings import APP_NAME, MIN_LEFT_PANEL_WIDTH, SPLITTER_RATIO_SIZES
from models.document import Document
from modules.converter.converter import ConverterRegistry
from ui.documents.doc_info import DocumentInfoWidget
from ui.documents.doc_tree import DocumentTreeWidget


class DocumentsTab(QWidget):
    """Интерфейс для работы с документами."""

    ontology_changed = Signal()  # документ добавлен/откачен/удалён из модели

    def __init__(self):
        super().__init__()
        self._pipeline = get_pipeline()
        self._doc_manager = get_doc_manager()

        # --- Левая панель ---
        self._upload_btn = QPushButton("Загрузить документ")
        self._tree = DocumentTreeWidget()

        left_panel = QWidget()
        left_panel.setMinimumWidth(MIN_LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._upload_btn)
        left_layout.addWidget(self._tree)

        # --- Правая панель ---
        self._info_widget = DocumentInfoWidget()

        # --- Основной макет ---
        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(self._info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(SPLITTER_RATIO_SIZES)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # --- Сигналы ---
        self._upload_btn.clicked.connect(self._on_doc_upload)
        self._tree.document_selected.connect(self._info_widget.set_document)
        self._info_widget.document_changed.connect(self._on_doc_info_changed)
        self._info_widget.document_deleted.connect(self._on_doc_deleted)
        self._info_widget.ontology_changed.connect(self.ontology_changed)

        self._tree.load_documents()

    def _on_doc_upload(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Выберите документы")
        if not file_paths:
            return

        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            file_name = file_path.name

            if not ConverterRegistry.is_format_supported(file_path.suffix.lower().replace(".", "")):
                QMessageBox.critical(self, APP_NAME, f'Формат документа "{file_name}" не поддерживается.')
                continue

            if self._doc_manager.is_file_exists(file_path):
                QMessageBox.warning(self, APP_NAME, f'Документ "{file_name}" уже существует в системе.')
                continue

            doc = self._doc_manager.add(file_path)

            res = self._pipeline.run(doc, final_stage=Document.Status.CLASS_DETERMINED)
            if not res and doc.status < Document.Status.CLASS_DETERMINED:
                self._doc_manager.delete(doc)
                QMessageBox.critical(self, APP_NAME, f'Не удалось извлечь UDDM из документа "{file_name}". {res.message}')
                continue
            elif not res:
                QMessageBox.warning(self, APP_NAME, f'Документ "{file_name}" был загружен, но класс не определен. {res.message}')

            self._doc_manager.save_metadata(doc)
            self._tree.add_or_update_document(doc)

    def _on_doc_info_changed(self, doc: Document):
        if doc is not None:
            self._tree.add_or_update_document(doc, select=True)

    def _on_doc_deleted(self, deleted_doc: Document):
        self._tree.remove_document(deleted_doc)
        self._info_widget.set_document(None)

    def apply_theme(self):
        """Обновляет виджеты, не покрытые делегатом дерева (дерево само подписано на смену темы)."""
        self._info_widget.apply_theme()

    def refresh_templates(self):
        """Обновляет список классов документов. Вызывается из MainWindow при изменении списка шаблонов."""
        selected = self._info_widget.get_document()
        self._tree.sync_groups_with_meta()
        self._info_widget.set_document(selected)
        self._info_widget.refresh_classes()

    def select_document_by_id(self, doc_id: str):
        """Активирует элемент дерева для документа с заданным id (если найден)."""
        self._tree.select_document_by_id(doc_id)
