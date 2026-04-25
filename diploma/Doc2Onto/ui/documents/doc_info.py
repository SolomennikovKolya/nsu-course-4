from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox,
    QPushButton, QMessageBox, QStackedLayout, QSizePolicy,
    QApplication
)

from app.context import get_pipeline, get_doc_manager, get_temp_manager
from app.settings import APP_NAME
from core.document import Document
from ui.common.editable_title import EditableTitleWidget
from ui.documents.status_bar import StatusBarWidget
from ui.documents.view.doc_view import DocumentViewWidget
from ui.common.design import DELETE_BUTTON_STYLE


class DocumentInfoWidget(QWidget):
    """Виджет для отображения информации о документе и управления его обработкой."""

    document_changed = Signal(Document)  # Сигнал, что информация о документе изменилась
    document_deleted = Signal(Document)  # Сигнал, что документ удален

    def __init__(self):
        super().__init__()
        self._pipeline = get_pipeline()
        self._doc_manager = get_doc_manager()
        self._temp_manager = get_temp_manager()
        self._document: Optional[Document] = None

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_empty_page())
        self._stack.addWidget(self._build_document_page())

    def _build_empty_page(self) -> QWidget:
        self._empty_page = QWidget()
        empty_layout = QVBoxLayout(self._empty_page)

        empty_label = QLabel("Выберите документ")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(empty_label)
        return self._empty_page

    def _build_document_page(self) -> QWidget:
        self._document_page = QWidget()
        page_layout = QVBoxLayout(self._document_page)

        # --- Заголовок ---
        self._title = EditableTitleWidget(
            placeholder="",
            title_style="font-size:16px;font-weight:bold;padding: 0px 4px 4px 4px;",
            subdued_style="color:#8a8a8a;",
        )
        self._title.committed.connect(self._on_rename_doc)
        page_layout.addWidget(self._title)

        # --- Класс ---
        self._class_combo = QComboBox()
        self._class_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._class_combo.addItem("Класс не определён", None)
        for doc_class in self._temp_manager.doc_classes_list():
            self._class_combo.addItem(doc_class, doc_class)

        self._class_combo.currentIndexChanged.connect(self._on_change_class)
        page_layout.addWidget(self._class_combo, 1)

        # --- Статус ---
        self._status_widget = StatusBarWidget()
        page_layout.addWidget(self._status_widget)
        page_layout.addSpacing(8)

        # --- Отображение документа ---
        self._document_view = DocumentViewWidget()
        self._document_view.setMinimumHeight(240)
        self._document_view.validation_result_changed.connect(self._on_validation_result_changed)
        page_layout.addWidget(self._document_view, 1)

        # --- Кнопки ---
        self._action_button = QPushButton()
        self._action_button.clicked.connect(self._on_run_pipeline)

        self._restart_button = QPushButton("Обработать заново")
        self._restart_button.clicked.connect(self._on_restart_pipeline)

        self._delete_button = QPushButton("Удалить документ")
        self._delete_button.setStyleSheet(DELETE_BUTTON_STYLE)
        self._delete_button.clicked.connect(self._on_delete_doc)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self._action_button)
        buttons_layout.addWidget(self._restart_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self._delete_button)
        page_layout.addLayout(buttons_layout)

        return self._document_page

    def set_document(self, document: Optional[Document]):
        """Установка документа в виджет."""
        self._document = document
        self._document_view.set_document(document)

        if document is None:
            self._stack.setCurrentWidget(self._empty_page)
            return

        self._stack.setCurrentWidget(self._document_page)

        # Обновляем данные на странице
        self._title.set_value(document.name)
        index = self._class_combo.findData(document.doc_class)
        if index >= 0:
            self._class_combo.setCurrentIndex(index)

        self._status_widget.set_status(document)
        self._update_buttons()

    def get_document(self) -> Optional[Document]:
        """Возвращает текущий документ."""
        return self._document

    def _on_rename_doc(self, new_name: str):
        doc = self._document
        if doc is None:
            return

        try:
            self._doc_manager.rename(doc, new_name)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, "Не удалось переименовать документ: " + str(e))
            self._title.set_value(doc.name)
            return

        self._title.set_value(new_name)
        self.document_changed.emit(doc)

    def _on_change_class(self):
        doc = self._document
        if doc is None:
            return

        new_class = self._class_combo.currentData()
        if doc.doc_class == new_class:
            return

        doc.doc_class = new_class

        # Обновляем статус документа в зависимости от нового класса
        if new_class is not None:
            doc.status = Document.Status.CLASS_DETERMINED
        else:
            if int(doc.status) >= int(Document.Status.UDDM_EXTRACTED):
                doc.status = Document.Status.UDDM_EXTRACTED

        doc.pipeline_failed_target = None
        doc.pipeline_error_message = None
        self._doc_manager.save_metadata(doc)

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_run_pipeline(self):
        doc = self._document
        if doc is None:
            return

        final_status = Document.Status.TRIPLES_BUILT
        if doc.status == final_status:
            final_status = Document.Status.ADDED_TO_MODEL

        self._pipeline.run(doc, final_status)
        self._doc_manager.save_metadata(doc)

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_restart_pipeline(self):
        doc = self._document
        if doc is None:
            return

        doc.status = Document.Status.UPLOADED
        res = self._pipeline.run(doc, Document.Status.TRIPLES_BUILT)
        self._doc_manager.save_metadata(doc)

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_delete_doc(self):
        doc = self._document
        if doc is None:
            return

        reply = QMessageBox.question(
            self, APP_NAME,
            "Вы точно хотите удалить документ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.set_document(None)
        QApplication.processEvents()

        self._doc_manager.delete(doc)
        self.document_deleted.emit(doc)

    def _on_validation_result_changed(self, doc: Document):
        self._status_widget.set_status(doc)
        self._update_buttons()

    def _update_buttons(self):
        self._update_action_button()
        self._update_restart_button()
        self._update_delete_button()

    def _update_action_button(self):
        doc = self._document

        if doc is None:
            self._action_button.setEnabled(False)
            self._action_button.setText("Выберите документ")
            return

        if doc.status == Document.Status.ADDED_TO_MODEL:
            self._action_button.setEnabled(False)
        else:
            self._action_button.setEnabled(True)

        match doc.status:
            case Document.Status.UPLOADED | Document.Status.UDDM_EXTRACTED:
                self._action_button.setText("Запустить обработку")
            case Document.Status.CLASS_DETERMINED | Document.Status.FIELDS_EXTRACTED | Document.Status.FIELDS_VALIDATED:
                self._action_button.setText("Продолжить обработку")
            case Document.Status.TRIPLES_BUILT:
                self._action_button.setText("Добавить в модель")
            case Document.Status.ADDED_TO_MODEL:
                self._action_button.setText("Документ добавлен в модель")

    def _update_restart_button(self):
        doc = self._document
        if doc is None:
            self._restart_button.setEnabled(False)
        else:
            self._restart_button.setEnabled(True)

    def _update_delete_button(self):
        doc = self._document
        if doc is None:
            self._delete_button.setEnabled(False)
        else:
            self._delete_button.setEnabled(True)

    def refresh_classes(self):
        """
        Обновляет список классов документов.
        Вызывается из `DocumentsTab.refresh_templates()`.
        """
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItem("Класс не определён", None)

        for doc_class in self._temp_manager.doc_classes_list():
            self._class_combo.addItem(doc_class, doc_class)

        if self._document is not None:
            index = self._class_combo.findData(self._document.doc_class)
            if index >= 0:
                self._class_combo.setCurrentIndex(index)

        self._class_combo.blockSignals(False)
