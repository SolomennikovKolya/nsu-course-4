from pathlib import Path
from typing import Dict, Optional, List
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter, QMessageBox
)

from app.context import get_pipeline, get_doc_manager
from app.settings import APP_NAME
from core.document import Document
from modules.converter.converter import ConverterRegistry
from ui.documents.doc_info import DocumentInfoWidget


class DocumentsCache:
    """Кеш документов, сгруппированных по классу."""

    def __init__(self):
        self._groups: Dict[str, List[Document]] = {}

    def clear(self):
        self._groups.clear()

    def load(self, documents: List[Document]):
        self.clear()
        for doc in documents:
            self.add_or_update(doc)

    def group_names(self) -> List[str]:
        return sorted(self._groups.keys())

    def docs_in_group(self, group: str) -> List[Document]:
        return self._groups.get(group, [])

    def add_or_update(self, doc: Document):
        self.remove(doc)
        key = self._group_key(doc)
        if key not in self._groups:
            self._groups[key] = []
        self._groups[key].append(doc)

    def remove(self, doc: Document):
        for group, docs in list(self._groups.items()):
            filtered = [d for d in docs if d is not doc and d.name != doc.name]
            if filtered:
                self._groups[group] = filtered
            else:
                del self._groups[group]

    @staticmethod
    def _group_key(doc: Document) -> str:
        return doc.doc_class if doc.doc_class else "Без класса"


class DocumentsTab(QWidget):
    """Интерфейс для работы с документами."""

    def __init__(self):
        super().__init__()
        self._pipeline = get_pipeline()
        self._doc_manager = get_doc_manager()
        self._docs_cache = DocumentsCache()

        # --- Список документов ---
        self._upload_btn = QPushButton("Загрузить документ")
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(20)

        tree_widget = QWidget()
        tree_widget.setMinimumWidth(250)
        tree_layout = QVBoxLayout(tree_widget)
        tree_layout.addWidget(self._upload_btn)
        tree_layout.addWidget(self._tree)

        # --- Информация о документе ---
        self._info_widget = DocumentInfoWidget()

        # --- Основной макет ---
        splitter = QSplitter()
        splitter.addWidget(tree_widget)
        splitter.addWidget(self._info_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(splitter)

        # --- Сигналы ---
        self._upload_btn.clicked.connect(self._on_doc_upload)
        self._tree.itemSelectionChanged.connect(self._on_doc_selection_changed)
        self._info_widget.document_changed.connect(self._on_doc_info_changed)
        self._info_widget.document_deleted.connect(self._on_doc_deleted)

        self._load_docs_cache()
        self._refresh_tree()

    def _on_doc_upload(self):
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

            if self._doc_manager.is_file_exists(file_path):
                QMessageBox.warning(self, APP_NAME, f'Документ "{file_name}" уже существует в системе.')
                continue

            doc = self._doc_manager.add(file_path)

            # Пытаемся извлечь UDDM сразу после загрузки
            res = self._pipeline.run(doc, final_stage=Document.Status.UDDM_EXTRACTED)
            if not res:
                self._doc_manager.delete(doc)
                QMessageBox.critical(self, APP_NAME, f'Не удалось извлечь данные из документа "{file_name}".')
                continue

            self._doc_manager.save_metadata(doc)
            self._docs_cache.add_or_update(doc)
            added_any = True

        if added_any:
            self._refresh_tree()

    def _on_doc_selection_changed(self):
        doc = self._get_selected_doc()
        self._info_widget.set_document(doc)

    def _get_selected_doc(self) -> Optional[Document]:
        item = self._tree.currentItem()
        if not item:
            return None

        doc = item.data(0, Qt.ItemDataRole.UserRole)
        return doc

    def _on_doc_info_changed(self, doc: Document):
        if doc is not None:
            self._docs_cache.add_or_update(doc)

        self._refresh_tree(selected_doc=doc, restore_focus=True)

    def _refresh_tree(self, selected_doc: Optional[Document] = None, restore_focus: bool = False):
        had_focus = restore_focus and self._tree.hasFocus()
        self._tree.clear()

        ordered_keys = self._docs_cache.group_names()

        for group in ordered_keys:
            folder = QTreeWidgetItem([group])
            folder.setFlags(folder.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            self._tree.addTopLevelItem(folder)

            for doc in self._docs_cache.docs_in_group(group):
                item = QTreeWidgetItem([doc.name])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)
                item.setForeground(0, self._get_doc_in_tree_color(doc.status))
                folder.addChild(item)

        self._tree.expandAll()
        if selected_doc is not None:
            self._select_doc_in_tree(selected_doc)
        if had_focus:
            self._tree.setFocus()

    def _select_doc_in_tree(self, doc_to_select: Document):
        for i in range(self._tree.topLevelItemCount()):
            folder = self._tree.topLevelItem(i)
            for j in range(folder.childCount()):
                item = folder.child(j)
                item_doc = item.data(0, Qt.ItemDataRole.UserRole)
                if item_doc is doc_to_select or (item_doc and item_doc.name == doc_to_select.name):
                    self._tree.blockSignals(True)
                    self._tree.setCurrentItem(item)
                    self._tree.blockSignals(False)
                    return

    def _get_doc_in_tree_color(self, doc_status: Document.Status) -> QColor:
        if doc_status == Document.Status.UPLOADED or doc_status == Document.Status.UDDM_EXTRACTED:
            return QColor("white")
        elif doc_status == Document.Status.ADDED_TO_MODEL:
            return QColor("#4CAF50")
        else:
            return QColor("#FFC107")

    def _on_doc_deleted(self, deleted_doc: Document):
        self._docs_cache.remove(deleted_doc)

        self._refresh_tree()
        self._info_widget.set_document(None)

    def refresh_templates(self):
        """
        Обновляет список классов документов. 
        Вызывается из MainWindow при изменении списка шаблонов (добавили новый, удалили или переименовали).
        """
        self._refresh_tree()
        self._info_widget.refresh_classes()

    def _load_docs_cache(self):
        """Однократная загрузка кеша документов с диска при создании вкладки."""
        self._docs_cache.load(self._doc_manager.list())
