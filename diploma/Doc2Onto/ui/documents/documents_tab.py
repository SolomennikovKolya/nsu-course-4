"""Вкладка для работы с документами: загрузка, отображение структуры, редактирование метаданных."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.context import get_doc_manager, get_events, get_pipeline
from app.settings import APP_NAME, MIN_LEFT_PANEL_WIDTH, SPLITTER_RATIO_SIZES
from models.document import Document
from modules.converter.converter import ConverterRegistry
from ui.documents.doc_info import DocumentInfoWidget
from ui.documents.doc_tree import DocumentTreeWidget


class DocumentsTab(QWidget):
    """Интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()
        self._pipeline = get_pipeline()
        self._doc_manager = get_doc_manager()
        self._build_ui()
        self._wire_signals()

    def _on_document_upload(self):
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
                QMessageBox.critical(
                    self, APP_NAME, f'Не удалось извлечь UDDM из документа "{file_name}". {res.message}'
                )
                continue
            elif not res:
                QMessageBox.warning(
                    self,
                    APP_NAME,
                    f'Документ "{file_name}" был загружен, но класс не определен. {res.message}',
                )

            self._doc_manager.save_metadata(doc)
            self._tree.add_or_update_document(doc)

    def _on_document_info_changed(self, doc: Document):
        self._tree.add_or_update_document(doc, select=True)
        self._info.set_document(doc)

    def _on_document_deleted(self, deleted_doc: Document):
        self._tree.remove_document(deleted_doc)
        self._info.set_document(None)

    def _on_templates_changed(self):
        selected = self._info.get_document()
        self._tree.sync_groups_with_meta()
        self._info.set_document(selected)
        self._info.refresh_classes()

    def _build_ui(self):
        self._upload_btn = QPushButton("Загрузить документ")
        self._tree = DocumentTreeWidget()

        left_panel = QWidget()
        left_panel.setMinimumWidth(MIN_LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._upload_btn)
        left_layout.addWidget(self._tree)

        self._info = DocumentInfoWidget()

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(self._info)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(SPLITTER_RATIO_SIZES)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def _wire_signals(self):
        self._upload_btn.clicked.connect(self._on_document_upload)
        self._tree.document_selection_changed.connect(self._info.set_document)
        self._info.document_info_changed.connect(self._on_document_info_changed)
        self._info.document_deleted.connect(self._on_document_deleted)

        events = get_events()
        events.templates_changed.connect(self._on_templates_changed)
        events.document_navigation_requested.connect(self._tree.select_document_by_id)
