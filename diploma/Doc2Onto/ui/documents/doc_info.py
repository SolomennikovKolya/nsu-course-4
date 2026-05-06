import json
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox,
    QPushButton, QMessageBox, QStackedLayout, QSizePolicy,
    QApplication, QDialog, QTextEdit, QDialogButtonBox
)

from app.context import get_pipeline, get_doc_manager, get_temp_manager, get_ontology_repository
from app.settings import APP_NAME
from models.document import Document
from ui.common.editable_title import EditableTitleWidget
from ui.documents.status_bar import StatusBarWidget
from ui.documents.view.doc_view import DocumentViewWidget
from ui.common.design import DELETE_BUTTON_STYLE


# Декларативная таблица доступных действий по статусу документа.
# Поля:
#   main:    тип главной кнопки ("run" | "continue" | "add" | "rollback")
#   restart: показывать ли кнопку «Перезапустить пайплайн»
#   delete:  активна ли кнопка удаления
#   class:   политика смены класса в combo:
#            "unlocked" — свободно;
#            "warn"     — спрашивать подтверждение;
#            "locked"   — combo дизаблен.
ACTIONS_BY_STATUS: Dict[Document.Status, Dict[str, Any]] = {
    Document.Status.UPLOADED:         {"main": "run",      "restart": False, "delete": True, "class": "unlocked"},
    Document.Status.UDDM_EXTRACTED:   {"main": "run",      "restart": False, "delete": True, "class": "unlocked"},
    Document.Status.CLASS_DETERMINED: {"main": "continue", "restart": True,  "delete": True, "class": "warn"},
    Document.Status.FIELDS_EXTRACTED: {"main": "continue", "restart": True,  "delete": True, "class": "warn"},
    Document.Status.FIELDS_VALIDATED: {"main": "continue", "restart": True,  "delete": True, "class": "warn"},
    Document.Status.TRIPLES_BUILT:    {"main": "add",      "restart": True,  "delete": True, "class": "warn"},
    Document.Status.ADDED_TO_MODEL:   {"main": "rollback", "restart": False, "delete": True, "class": "locked"},
}

_MAIN_LABELS = {
    "run":       "Запустить обработку",
    "continue":  "Продолжить обработку",
    "add":       "Добавить в модель",
    "rollback":  "Откатить из модели",
}


class DocumentInfoWidget(QWidget):
    """Виджет для отображения информации о документе и управления его обработкой."""

    document_changed = Signal(Document)
    document_deleted = Signal(Document)
    ontology_changed = Signal()

    def __init__(self):
        super().__init__()
        self._pipeline = get_pipeline()
        self._doc_manager = get_doc_manager()
        self._temp_manager = get_temp_manager()
        self._repo = get_ontology_repository()
        self._document: Optional[Document] = None

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._build_empty_page())
        self._stack.addWidget(self._build_document_page())

    # ------------------------------------------------------------ pages

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

        self._title = EditableTitleWidget(
            placeholder="",
            title_style="font-size:16px;font-weight:bold;padding: 0px 4px 4px 4px;",
            subdued_style="color:#8a8a8a;",
        )
        self._title.committed.connect(self._on_rename_doc)
        page_layout.addWidget(self._title)

        self._class_combo = QComboBox()
        self._class_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._class_combo.addItem("Класс не определён", None)
        for t in self._temp_manager.list():
            self._class_combo.addItem(t.name, t.id)
        self._class_combo.currentIndexChanged.connect(self._on_change_class)
        page_layout.addWidget(self._class_combo, 1)

        self._status_widget = StatusBarWidget()
        page_layout.addWidget(self._status_widget)
        page_layout.addSpacing(8)

        self._document_view = DocumentViewWidget()
        self._document_view.setMinimumHeight(240)
        page_layout.addWidget(self._document_view, 1)

        self._action_button = QPushButton()
        self._action_button.clicked.connect(self._on_action_clicked)

        self._restart_button = QPushButton("Перезапустить пайплайн")
        self._restart_button.clicked.connect(self._on_restart_pipeline)

        self._changes_button = QPushButton("Что изменилось")
        self._changes_button.clicked.connect(self._on_show_changes)

        self._delete_button = QPushButton("Удалить документ")
        self._delete_button.setStyleSheet(DELETE_BUTTON_STYLE)
        self._delete_button.clicked.connect(self._on_delete_doc)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self._action_button)
        buttons_layout.addWidget(self._changes_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self._restart_button)
        buttons_layout.addWidget(self._delete_button)
        page_layout.addLayout(buttons_layout)

        return self._document_page

    # ------------------------------------------------------------ public API

    def set_document(self, document: Optional[Document]):
        self._document = document
        self._document_view.set_document(document)

        if document is None:
            self._title.setToolTip("")
            self._stack.setCurrentWidget(self._empty_page)
            return

        self._stack.setCurrentWidget(self._document_page)

        self._title.setToolTip(f"ID: {document.id}")
        self._title.set_value(document.name)

        self._class_combo.blockSignals(True)
        index = self._class_combo.findData(document.doc_class)
        if index >= 0:
            self._class_combo.setCurrentIndex(index)
        self._class_combo.blockSignals(False)

        self._status_widget.set_status(document)
        self._update_buttons()

    def get_document(self) -> Optional[Document]:
        return self._document

    def refresh_classes(self):
        """Обновляет список классов в комбо-боксе при изменении набора шаблонов."""
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItem("Класс не определён", None)

        for t in self._temp_manager.list():
            self._class_combo.addItem(t.name, t.id)

        if self._document is not None:
            index = self._class_combo.findData(self._document.doc_class)
            if index >= 0:
                self._class_combo.setCurrentIndex(index)

        self._class_combo.blockSignals(False)

    # ------------------------------------------------------------ slots

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

        policy = ACTIONS_BY_STATUS.get(doc.status, {}).get("class", "unlocked")
        if policy == "locked":
            QMessageBox.information(
                self, APP_NAME,
                "Документ добавлен в модель. Чтобы изменить класс, сначала откатите его из модели."
            )
            self._class_combo.blockSignals(True)
            idx = self._class_combo.findData(doc.doc_class)
            if idx >= 0:
                self._class_combo.setCurrentIndex(idx)
            self._class_combo.blockSignals(False)
            return

        if policy == "warn":
            reply = QMessageBox.question(
                self, APP_NAME,
                "Изменение класса сбросит результаты извлечения и валидации, "
                "ваши правки в графе будут потеряны. Продолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._class_combo.blockSignals(True)
                idx = self._class_combo.findData(doc.doc_class)
                if idx >= 0:
                    self._class_combo.setCurrentIndex(idx)
                self._class_combo.blockSignals(False)
                return

        doc.doc_class = new_class

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

    def _on_action_clicked(self):
        doc = self._document
        if doc is None:
            return
        action = ACTIONS_BY_STATUS.get(doc.status, {}).get("main")

        if action in ("run", "continue", "add"):
            self._run_pipeline_to_appropriate_target(doc)
        elif action == "rollback":
            self._on_rollback()

    def _run_pipeline_to_appropriate_target(self, doc: Document):
        target = Document.Status.TRIPLES_BUILT if doc.status == Document.Status.UPLOADED \
            or int(doc.status) < int(Document.Status.TRIPLES_BUILT) else Document.Status.ADDED_TO_MODEL
        if doc.status == Document.Status.TRIPLES_BUILT:
            target = Document.Status.ADDED_TO_MODEL

        self._pipeline.run(doc, target)
        self._doc_manager.save_metadata(doc)

        if doc.status == Document.Status.ADDED_TO_MODEL:
            self.ontology_changed.emit()

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_restart_pipeline(self):
        doc = self._document
        if doc is None:
            return

        if doc.status == Document.Status.ADDED_TO_MODEL:
            QMessageBox.information(
                self, APP_NAME,
                "Документ добавлен в модель. Откатите его сначала."
            )
            return

        reply = QMessageBox.question(
            self, APP_NAME,
            "Перезапустить пайплайн? Все промежуточные результаты будут пересчитаны.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        doc.status = Document.Status.UPLOADED
        self._pipeline.run(doc, Document.Status.TRIPLES_BUILT)
        self._doc_manager.save_metadata(doc)

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_rollback(self):
        doc = self._document
        if doc is None:
            return

        reply = QMessageBox.question(
            self, APP_NAME,
            "Откатить документ из модели? Артефакты документа сохранятся.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._repo.rollback_document(doc.id)
        except Exception as ex:
            QMessageBox.warning(self, APP_NAME, f"Не удалось откатить документ: {ex}")
            return

        doc.status = Document.Status.TRIPLES_BUILT
        doc.pipeline_failed_target = None
        doc.pipeline_error_message = None
        self._doc_manager.save_metadata(doc)

        self.ontology_changed.emit()

        self._status_widget.set_status(doc)
        self._update_buttons()
        self._document_view.set_document(doc)
        self.document_changed.emit(doc)

    def _on_delete_doc(self):
        doc = self._document
        if doc is None:
            return

        is_in_model = doc.status == Document.Status.ADDED_TO_MODEL
        text = (
            "Документ добавлен в модель. При удалении его факты будут откачены.\n\nПродолжить?"
            if is_in_model else
            "Вы точно хотите удалить документ?"
        )
        reply = QMessageBox.question(
            self, APP_NAME, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if is_in_model:
            try:
                self._repo.rollback_document(doc.id)
                self.ontology_changed.emit()
            except Exception as ex:
                QMessageBox.warning(self, APP_NAME, f"Не удалось откатить документ перед удалением: {ex}")
                return

        self.set_document(None)
        QApplication.processEvents()

        self._doc_manager.delete(doc)
        self.document_deleted.emit(doc)

    def _on_show_changes(self):
        doc = self._document
        if doc is None:
            return

        report_path = doc.ontology_merge_report_file_path()
        if not report_path.exists():
            QMessageBox.information(self, APP_NAME, "Отчёт о слиянии для документа отсутствует.")
            return

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as ex:
            QMessageBox.warning(self, APP_NAME, f"Не удалось прочитать отчёт: {ex}")
            return

        text = self._format_change_report(report)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Что изменилось — {doc.name}")
        dlg.resize(720, 480)
        layout = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        bb.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dlg.accept)
        layout.addWidget(bb)
        dlg.exec()

    @staticmethod
    def _format_change_report(report: dict) -> str:
        lines = []
        lines.append(f"Документ: {report.get('document_id')}")
        if report.get('effective_date'):
            lines.append(f"Дата документа: {report.get('effective_date')}")
        lines.append("")

        changes = report.get("changes") or []
        rejected = report.get("rejected") or []

        added = [c for c in changes if c.get("event") == "added"]
        replaced = [c for c in changes if c.get("event") == "replaced"]

        if added:
            lines.append(f"Добавлено новых фактов: {len(added)}")
            for c in added:
                lines.append(f"  + ({c['subject_n3']} {c['predicate_n3']} {c['object_n3']})  [{c.get('policy', '?')}]")
            lines.append("")

        if replaced:
            lines.append(f"Заменено фактов: {len(replaced)}")
            for c in replaced:
                lines.append(
                    f"  ~ ({c['subject_n3']} {c['predicate_n3']} {c['object_n3']})  [{c.get('policy', '?')}]"
                )
                if c.get("superseded_object_n3"):
                    lines.append(f"      ↳ заменено: {c['superseded_object_n3']}")
            lines.append("")

        if rejected:
            lines.append(f"Отклонено фактов (старее существующих): {len(rejected)}")
            for c in rejected:
                lines.append(
                    f"  ! ({c['subject_n3']} {c['predicate_n3']} {c['object_n3']})  [{c.get('policy', '?')}]"
                )
            lines.append("")

        if not added and not replaced and not rejected:
            lines.append("Изменений нет.")
        return "\n".join(lines)

    # ------------------------------------------------------------ buttons state

    def _update_buttons(self):
        doc = self._document

        if doc is None:
            self._action_button.setEnabled(False)
            self._action_button.setText("Выберите документ")
            self._restart_button.setVisible(False)
            self._restart_button.setEnabled(False)
            self._changes_button.setVisible(False)
            self._delete_button.setEnabled(False)
            return

        meta = ACTIONS_BY_STATUS.get(doc.status, {})
        main_kind = meta.get("main", "run")

        self._action_button.setText(_MAIN_LABELS.get(main_kind, "..."))

        # Если класс не задан и нужен — главную кнопку отключаем
        if doc.doc_class is None and main_kind in ("run", "continue", "add"):
            self._action_button.setEnabled(int(doc.status) <= int(Document.Status.UDDM_EXTRACTED) is False)
            if doc.status in (Document.Status.UPLOADED, Document.Status.UDDM_EXTRACTED):
                self._action_button.setEnabled(False)
        else:
            self._action_button.setEnabled(True)

        self._restart_button.setVisible(bool(meta.get("restart", False)))
        self._restart_button.setEnabled(bool(meta.get("restart", False)))
        self._delete_button.setEnabled(bool(meta.get("delete", True)))

        self._changes_button.setVisible(doc.status == Document.Status.ADDED_TO_MODEL)
        self._changes_button.setEnabled(doc.status == Document.Status.ADDED_TO_MODEL)

        if meta.get("class") == "locked":
            self._class_combo.setEnabled(False)
        else:
            self._class_combo.setEnabled(True)
