from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QComboBox, QPushButton,
    QMessageBox, QStackedLayout
)
from PySide6.QtCore import Qt, Signal
from typing import Optional

from app.context import get_pipeline, get_doc_manager, get_temp_manager
from app.utils import require_attribute
from core.document import Document
from ui.documents.status_progress_widget import StatusProgressWidget


def require_document(method):
    """Проверяет наличие документа перед выполнением метода."""
    return require_attribute("document")(method)


class DocumentInfoWidget(QWidget):
    """Виджет для отображения информации о документе и управления его обработкой."""

    documents_tree_changed = Signal()
    document_deleted = Signal()  # Немного отличается от documents_tree_changed, т.к. надо вызвать дополнительные действия

    def __init__(self):
        super().__init__()

        self.pipeline = get_pipeline()
        self.doc_manager = get_doc_manager()
        self.temp_manager = get_temp_manager()
        self.document: Optional[Document] = None

        self.stack = QStackedLayout(self)
        self.stack.addWidget(self.build_empty_page())
        self.stack.addWidget(self.build_document_page())

    def build_empty_page(self) -> QWidget:
        """Страница, отображаемая при отсутствии выбранного документа."""
        self.page_empty = QWidget()
        empty_layout = QVBoxLayout(self.page_empty)

        self.empty_label = QLabel("Выберите документ")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        return self.page_empty

    def build_document_page(self) -> QWidget:
        """Страница с информацией о документе и кнопками управления обработкой."""
        # Название
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size:16px;font-weight:bold")

        # Класс
        self.class_combo = QComboBox()
        self.class_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.class_combo.addItem("Не определён", None)
        for doc_class in self.temp_manager.doc_classes_list():
            self.class_combo.addItem(doc_class, doc_class)

        self.class_combo.currentIndexChanged.connect(self.change_class)

        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("Класс:"))
        class_layout.addWidget(self.class_combo)
        class_layout.addStretch()

        # Статус
        self.status_widget = StatusProgressWidget()

        # Кнопки
        self.action_button = QPushButton()
        self.action_button.clicked.connect(self.run_action)

        self.restart_button = QPushButton("Обработать заново")
        self.restart_button.setMaximumWidth(140)
        self.restart_button.clicked.connect(self.restart_action)

        self.delete_button = QPushButton("Удалить документ")
        self.delete_button.setMaximumWidth(140)
        self.delete_button.setStyleSheet("""
        QPushButton:hover {
            background-color: #d32f2f;
            color: white;
        }
        """)
        self.delete_button.clicked.connect(self.delete_action)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.action_button)
        buttons_layout.addWidget(self.restart_button)
        buttons_layout.addWidget(self.delete_button)

        # Сборка всей страницы
        self.page_document = QWidget()
        self.page_layout = QVBoxLayout(self.page_document)

        self.page_layout.addWidget(self.title)
        self.page_layout.addLayout(class_layout)
        self.page_layout.addWidget(QLabel("Статус:"))
        self.page_layout.addWidget(self.status_widget)
        self.page_layout.addStretch()
        self.page_layout.addLayout(buttons_layout)

        return self.page_document

    def set_document(self, document: Optional[Document]):
        self.document = document

        if document is None:
            self.stack.setCurrentWidget(self.page_empty)
            return

        self.stack.setCurrentWidget(self.page_document)

        # Обновляем данные на странице
        self.title.setText(document.name)
        index = self.class_combo.findData(document.doc_class)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)

        self.status_widget.set_status(document.status)
        self.update_buttons()

    def change_class(self):
        doc = self.document
        if doc is None:
            return

        new_class = self.class_combo.currentData()
        if doc.doc_class == new_class:
            return

        doc.doc_class = new_class
        if new_class is not None:
            doc.status = Document.Status.CLASS_DETERMINED
            doc.template = self.temp_manager.get(new_class)
        elif int(doc.status) >= int(Document.Status.UDDM_EXTRACTED):
            doc.status = Document.Status.UDDM_EXTRACTED

        self.doc_manager.save_metadata(doc)

        self.status_widget.set_status(doc.status)
        self.update_buttons()
        self.documents_tree_changed.emit()

    @require_document
    def run_action(self, doc: Document):
        self.pipeline.run(doc)
        self.doc_manager.save_metadata(doc)

        self.status_widget.set_status(doc.status)
        self.update_buttons()
        self.documents_tree_changed.emit()

    @require_document
    def restart_action(self, doc: Document):
        doc.status = Document.Status.UPLOADED
        self.pipeline.run(doc, Document.Status.ADDED_TO_MODEL)
        self.doc_manager.save_metadata(doc)

        self.status_widget.set_status(doc.status)
        self.update_buttons()
        self.documents_tree_changed.emit()

    @require_document
    def delete_action(self, doc: Document):
        reply = QMessageBox.question(
            self,
            "Удаление документа",
            "Вы точно хотите удалить документ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.doc_manager.delete(doc)

        self.set_document(None)
        self.document_deleted.emit()

    def update_buttons(self):
        self.update_action_button()
        self.update_restart_button()
        self.update_delete_button()

    def update_action_button(self):
        doc = self.document

        if doc is None:
            self.action_button.setEnabled(False)
            self.action_button.setText("Выберите документ")
            return

        if doc.doc_class is None:
            self.action_button.setEnabled(False)
            self.action_button.setText("Выберите класс документа")
            return

        if doc.status == Document.Status.ADDED_TO_MODEL:
            self.action_button.setEnabled(False)
            self.action_button.setText("Документ добавлен в модель")
            return

        self.action_button.setEnabled(True)

        if int(doc.status) <= int(Document.Status.CLASS_DETERMINED):
            self.action_button.setText("Запустить обработку")
        elif doc.status == Document.Status.TERMS_VALIDATED:
            self.action_button.setText("Добавить в модель")
        else:
            self.action_button.setText("Продолжить обработку")

    def update_restart_button(self):
        doc = self.document
        if doc is None or doc.status == Document.Status.UPLOADED:
            self.restart_button.setEnabled(False)
        else:
            self.restart_button.setEnabled(True)

    def update_delete_button(self):
        doc = self.document
        if doc is None:
            self.delete_button.setEnabled(False)
        else:
            self.delete_button.setEnabled(True)

    def refresh_classes(self):
        current = self.class_combo.currentData()

        self.class_combo.blockSignals(True)

        self.class_combo.clear()
        self.class_combo.addItem("Не определён", None)

        for doc_class in self.temp_manager.doc_classes_list():
            self.class_combo.addItem(doc_class, doc_class)

        index = self.class_combo.findData(current)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)

        self.class_combo.blockSignals(False)
