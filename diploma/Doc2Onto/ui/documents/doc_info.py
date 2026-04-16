from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QPushButton,
    QMessageBox, QStackedLayout, QSizePolicy
)

from app.context import get_pipeline, get_doc_manager, get_temp_manager
from app.settings import APP_NAME
from app.utils import require_attribute
from core.document import Document
from ui.common.editable_title import EditableTitleWidget
from ui.documents.status_bar import StatusBarWidget
from ui.documents.view.doc_view import DocumentViewWidget


def require_document(method):
    """Проверяет наличие документа перед выполнением метода."""
    return require_attribute("document")(method)


class DocumentInfoWidget(QWidget):
    """Виджет для отображения информации о документе и управления его обработкой."""

    document_changed = Signal()  # Сигнал, что информация о документе изменилась
    document_deleted = Signal()  # Сигнал, что документ удален

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
        return self.page_empty

    def build_document_page(self) -> QWidget:
        """Страница с информацией о документе и кнопками управления обработкой."""
        self.page_document = QWidget()
        self.page_layout = QVBoxLayout(self.page_document)

        # --- Заголовок ---
        self.title = EditableTitleWidget(
            placeholder="",
            title_style="font-size:16px;font-weight:bold;padding: 0px 4px 4px 4px;",
            subdued_style="color:#8a8a8a;",
        )
        self.title.committed.connect(self.rename_document)
        self.page_layout.addWidget(self.title)

        # --- Класс ---
        self.class_combo = QComboBox()
        self.class_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.class_combo.addItem("Класс не определён", None)
        for doc_class in self.temp_manager.doc_classes_list():
            self.class_combo.addItem(doc_class, doc_class)

        self.class_combo.currentIndexChanged.connect(self.change_class)

        self.page_layout.addWidget(self.class_combo, 1)

        # --- Статус ---
        self.status_widget = StatusBarWidget()
        self.page_layout.addWidget(self.status_widget)

        self.page_layout.addSpacing(8)

        # --- Отображение документа ---
        self.document_view = DocumentViewWidget()
        self.document_view.setMinimumHeight(240)
        self.page_layout.addWidget(self.document_view, 1)

        # --- Кнопки ---
        self.action_button = QPushButton()
        self.action_button.clicked.connect(self.run_action)

        self.restart_button = QPushButton("Обработать заново")
        self.restart_button.clicked.connect(self.restart_action)

        self.delete_button = QPushButton("Удалить документ")
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
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.delete_button)
        self.page_layout.addLayout(buttons_layout)

        return self.page_document

    def set_document(self, document: Optional[Document]):
        """Установка документа в виджет."""
        self.document = document
        self.document_view.set_document(document)

        if document is None:
            self.stack.setCurrentWidget(self.page_empty)
            return

        self.stack.setCurrentWidget(self.page_document)

        # Обновляем данные на странице
        self.title.set_value(document.name)
        index = self.class_combo.findData(document.doc_class)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)

        self.status_widget.set_status(document.status)
        self.update_buttons()

    @require_document
    def rename_document(self, doc: Document, new_name: str):
        try:
            self.doc_manager.rename(doc, new_name)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            self.title.set_value(doc.name)
            return
        self.title.set_value(new_name)
        self.document_changed.emit()

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
        self.document_changed.emit()

    @require_document
    def run_action(self, doc: Document):
        self.pipeline.run(doc)
        self.doc_manager.save_metadata(doc)

        self.status_widget.set_status(doc.status, doc.failed_status)
        self.update_buttons()
        self.document_changed.emit()

    @require_document
    def restart_action(self, doc: Document):
        doc.status = Document.Status.UPLOADED
        self.pipeline.run(doc, Document.Status.ADDED_TO_MODEL)
        self.doc_manager.save_metadata(doc)

        self.status_widget.set_status(doc.status, doc.failed_status)
        self.update_buttons()
        self.document_changed.emit()

    @require_document
    def delete_action(self, doc: Document):
        reply = QMessageBox.question(
            self,
            APP_NAME,
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
        if doc is None:
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
        self.class_combo.blockSignals(True)

        self.class_combo.clear()
        self.class_combo.addItem("Класс не определён", None)

        for doc_class in self.temp_manager.doc_classes_list():
            self.class_combo.addItem(doc_class, doc_class)

        if self.document is not None:
            index = self.class_combo.findData(self.document.doc_class)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)

        self.class_combo.blockSignals(False)
