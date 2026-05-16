"""Дерево документов: группировка по классам, кеш, раскраска через делегат темы."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QStyle, QStyleOptionViewItem, QStyledItemDelegate,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.context import get_temp_manager, get_doc_manager, get_theme_manager
from models.document import Document


# UserRole — объект Document; KindRole — семантический тон строки для раскраски.
_TREE_KIND_ROLE = Qt.ItemDataRole.UserRole + 1


class _DocumentTreeKind:
    """Семантические роли строк дерева."""

    FOLDER = "folder"
    DOC_DEFAULT = "doc_default"
    DOC_COMPLETE = "doc_complete"
    DOC_IN_PROGRESS = "doc_in_progress"


def _doc_tree_kind_from_status(status: Document.Status) -> str:
    if status in (
        Document.Status.UPLOADED,
        Document.Status.UDDM_EXTRACTED,
        Document.Status.CLASS_DETERMINED,
    ):
        return _DocumentTreeKind.DOC_DEFAULT
    if status == Document.Status.ADDED_TO_MODEL:
        return _DocumentTreeKind.DOC_COMPLETE
    return _DocumentTreeKind.DOC_IN_PROGRESS


class _DocumentsTreeDelegate(QStyledItemDelegate):
    """Читает KindRole и красит текст актуальными токенами темы."""

    def paint(self, painter, option: QStyleOptionViewItem, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        kind = index.data(_TREE_KIND_ROLE)
        if not isinstance(kind, str):
            doc = index.data(Qt.ItemDataRole.UserRole)
            kind = (
                _doc_tree_kind_from_status(doc.status)
                if isinstance(doc, Document)
                else _DocumentTreeKind.FOLDER
            )

        if not (opt.state & QStyle.StateFlag.State_Selected):
            color = QColor(get_theme_manager().current.color_for_doc_tree_kind(kind))
            opt.palette.setColor(QPalette.ColorRole.Text, color)

        super().paint(painter, opt, index)


class _DocumentsCache:
    """Кеш документов, сгруппированных по классу."""

    def __init__(self):
        self._doc_manager = get_doc_manager()
        self._groups: Dict[str, List[Document]] = {}

    def clear(self):
        self._groups.clear()

    def load(self):
        self.clear()
        for doc in self._doc_manager.iterate():
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
        self._groups[key].sort(key=lambda d: d.name.lower())

    def remove(self, doc: Document):
        for group, docs in list(self._groups.items()):
            filtered = [d for d in docs if d is not doc and d.id != doc.id]
            if filtered:
                self._groups[group] = filtered
            else:
                del self._groups[group]

    def sync_groups_with_meta(self):
        """Перечитывает метаданные для всех закешированных документов и пересобирает группы."""
        docs: List[Document] = []
        for group_docs in self._groups.values():
            docs.extend(group_docs)
        for doc in docs:
            get_doc_manager().reload_metadata(doc)

        self.clear()
        for doc in docs:
            self.add_or_update(doc)

    @staticmethod
    def _group_key(doc: Document) -> str:
        if not doc.doc_class:
            return "Без класса"
        t = get_temp_manager().get(doc.doc_class)
        return t.name if t else "Неизвестный класс"


class DocumentTreeWidget(QWidget):
    """Дерево документов, сгруппированное по классам, с собственным кешем и раскраской по теме."""

    document_selected = Signal(object)  # Document | None

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._cache = _DocumentsCache()

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(20)
        self._tree.setItemDelegate(_DocumentsTreeDelegate(self._tree))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    # ---------- public API ----------

    def load_documents(self):
        """Полная загрузка кеша документов (с перерисовкой дерева)."""
        self._cache.load()
        self._refresh()

    def add_or_update_document(self, doc: Document, *, select: bool = False):
        """Добавить или обновить документ; при ``select=True`` выделить его в дереве."""
        self._cache.add_or_update(doc)
        self._refresh(selected_doc=doc if select else None, restore_focus=select)

    def remove_document(self, doc: Document):
        self._cache.remove(doc)
        self._refresh()

    def sync_groups_with_meta(self):
        """Перечитывает метаданные и перестраивает группы (например, после изменения шаблонов)."""
        selected = self.current_document()
        self._cache.sync_groups_with_meta()
        self._refresh(selected_doc=selected, restore_focus=True)

    def current_document(self) -> Optional[Document]:
        """Возвращает выделенный в дереве документ или None, если ничего не выделено или выделена папка."""
        item = self._tree.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def select_document_by_id(self, doc_id: str) -> bool:
        """Выделить документ по id; возвращает True, если документ найден."""
        for group in self._cache.group_names():
            for doc in self._cache.docs_in_group(group):
                if doc.id == doc_id:
                    self._select_in_tree(doc)
                    return True
        return False

    # ---------- slots ----------

    def _on_selection_changed(self):
        self.document_selected.emit(self.current_document())

    def _on_theme_changed(self, _theme_id: str):
        self._tree.viewport().update()

    # ---------- internals ----------

    def _refresh(self, selected_doc: Optional[Document] = None, restore_focus: bool = False):
        had_focus = restore_focus and self._tree.hasFocus()
        self._tree.clear()

        for group in self._cache.group_names():
            folder = QTreeWidgetItem([group])
            folder.setFlags(folder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            folder.setData(0, _TREE_KIND_ROLE, _DocumentTreeKind.FOLDER)
            self._tree.addTopLevelItem(folder)

            for doc in self._cache.docs_in_group(group):
                item = QTreeWidgetItem([doc.name])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)
                item.setData(0, _TREE_KIND_ROLE, _doc_tree_kind_from_status(doc.status))
                folder.addChild(item)

        self._tree.expandAll()
        if selected_doc is not None:
            self._select_in_tree(selected_doc)
        if had_focus:
            self._tree.setFocus()

    def _select_in_tree(self, doc_to_select: Document):
        for i in range(self._tree.topLevelItemCount()):
            folder = self._tree.topLevelItem(i)
            for j in range(folder.childCount()):
                item = folder.child(j)
                item_doc = item.data(0, Qt.ItemDataRole.UserRole)
                if item_doc is doc_to_select or (item_doc and item_doc.id == doc_to_select.id):
                    self._tree.blockSignals(True)
                    self._tree.setCurrentItem(item)
                    self._tree.blockSignals(False)
                    return
