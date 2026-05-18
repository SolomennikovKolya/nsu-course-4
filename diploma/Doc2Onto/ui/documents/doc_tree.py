"""Дерево документов: группировка по классам, кеш, раскраска через делегат темы."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.context import get_doc_manager, get_temp_manager
from models.document import Document
from ui.common.item_delegate import ITEM_KIND_ROLE, ThemedItemDelegate


def _kind_for_doc_status(status: Document.Status) -> str | None:
    """Возвращает kind для делегата по статусу документа."""
    if status == Document.Status.ADDED_TO_MODEL:
        return "severity_success"
    if status in (
        Document.Status.UPLOADED,
        Document.Status.UDDM_EXTRACTED,
        Document.Status.CLASS_DETERMINED,
    ):
        return None  # дефолтный цвет темы
    return "severity_warning"


class _DocumentsCache:
    """Кеш документов, сгруппированных по классу."""

    def __init__(self):
        self._doc_manager = get_doc_manager()
        self._groups: dict[str, list[Document]] = {}

    def clear(self):
        self._groups.clear()

    def load(self):
        self.clear()
        for doc in self._doc_manager.iterate():
            self.add_or_update(doc)

    def group_names(self) -> list[str]:
        return sorted(self._groups.keys())

    def docs_in_group(self, group: str) -> list[Document]:
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
        docs: list[Document] = []
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

    document_selection_changed = Signal(object)  # Document | None

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cache = _DocumentsCache()
        self._cache.load()
        self._build_ui()
        self._wire_signals()
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

    def current_document(self) -> Document | None:
        """Возвращает выделенный документ или ``None``, если ничего не выделено."""
        item = self._tree.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def select_document_by_id(self, doc_id: str) -> bool:
        """Выделить документ по id; возвращает ``True``, если документ найден."""
        for group in self._cache.group_names():
            for doc in self._cache.docs_in_group(group):
                if doc.id == doc_id:
                    self._select_in_tree(doc)
                    return True
        return False

    def _on_selection_changed(self):
        self.document_selection_changed.emit(self.current_document())

    def _build_ui(self):
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(20)
        self._tree.setItemDelegate(ThemedItemDelegate(self._tree))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def _wire_signals(self):
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

    def _refresh(self, selected_doc: Document | None = None, restore_focus: bool = False):
        had_focus = restore_focus and self._tree.hasFocus()
        self._tree.clear()

        italic_font = QFont(self._tree.font())
        italic_font.setItalic(True)

        for group in self._cache.group_names():
            folder = QTreeWidgetItem([group])
            folder.setFlags(folder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            folder.setFont(0, italic_font)
            self._tree.addTopLevelItem(folder)

            for doc in self._cache.docs_in_group(group):
                item = QTreeWidgetItem([doc.name])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)
                kind = _kind_for_doc_status(doc.status)
                if kind:
                    item.setData(0, ITEM_KIND_ROLE, kind)
                folder.addChild(item)

        self._tree.expandAll()
        if selected_doc is not None:
            self._select_in_tree(selected_doc)
        if had_focus:
            self._tree.setFocus()

    def _select_in_tree(self, doc_to_select: Document):
        for i in range(self._tree.topLevelItemCount()):
            folder = self._tree.topLevelItem(i)
            if folder is None:
                continue

            for j in range(folder.childCount()):
                item = folder.child(j)
                item_doc = item.data(0, Qt.ItemDataRole.UserRole)
                if item_doc is doc_to_select or (item_doc and item_doc.id == doc_to_select.id):
                    self._tree.blockSignals(True)
                    self._tree.setCurrentItem(item)
                    self._tree.blockSignals(False)
                    return
