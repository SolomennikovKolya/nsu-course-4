from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import get_doc_manager, get_temp_manager
from app.paths import project_root
from core.template.template import Template
from ui.templates.python_code_html import plain_message_to_preview_html, python_code_to_preview_html
from ui.common.utils import show_warning_dialog


def _open_template_code_in_editor(code_path: Path) -> None:
    """
    Открывает code.py в VS Code / Cursor с корнем проекта как workspace — иначе Pylance не видит импорты (core, app, …).

    Вызываем ``code . <относительный_путь>`` с ``cwd`` = корень проекта; при несовпадении дисков — ``code <root> <file>``.
    """
    root = project_root()
    code_abs = code_path.resolve()
    for cmd in ("code", "cursor"):
        exe = shutil.which(cmd)
        if not exe:
            continue
        try:
            rel = code_abs.relative_to(root)
        except ValueError:
            subprocess.Popen([exe, str(root), str(code_abs)], cwd=str(root))
        else:
            subprocess.Popen([exe, ".", str(rel)], cwd=str(root))
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(code_abs)))


class TemplateInfoWidget(QWidget):
    """Правая панель: метаданные шаблона, предпросмотр кода, действия."""

    template_name_changed = Signal()  # Сигнал, что имя шаблона изменилось
    template_deleted = Signal()       # Сигнал, что шаблон удален

    def __init__(self):
        super().__init__()

        self.temp_manager = get_temp_manager()
        self.template: Optional[Template] = None
        self._loading_fields = False

        self._desc_timer = QTimer(self)
        self._desc_timer.setSingleShot(True)
        self._desc_timer.timeout.connect(self._flush_description)

        self.stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.stack.addWidget(self._build_empty_page())
        self.stack.addWidget(self._build_detail_page())

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lab = QLabel("Выберите шаблон")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lab)
        lay.addStretch()
        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)

        lay.addWidget(QLabel("Название шаблона:"))
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_name_editing_finished)
        lay.addWidget(self.name_edit)

        lay.addWidget(QLabel("Описание:"))
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Краткое описание шаблона…")
        self.description_edit.setMaximumHeight(100)
        self.description_edit.textChanged.connect(self._on_description_changed)
        lay.addWidget(self.description_edit)

        lay.addWidget(QLabel("Предпросмотр кода:"))
        self.code_preview = QTextBrowser()
        self.code_preview.setReadOnly(True)
        self.code_preview.setOpenExternalLinks(False)
        lay.addWidget(self.code_preview, 1)

        btn_row = QHBoxLayout()
        self.edit_btn = QPushButton("Редактировать шаблон")
        self.edit_btn.setToolTip("Открыть code.py в VS Code (если доступен командой code), иначе в редакторе по умолчанию")
        self.edit_btn.clicked.connect(self._on_edit_code)
        self.delete_btn = QPushButton("Удалить шаблон")
        self.delete_btn.clicked.connect(self._on_delete_template)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        return page

    def current_template_name(self) -> Optional[str]:
        return self.template.name if self.template else None

    def set_template(self, template: Optional[Template]):
        self.template = template
        if template is None:
            self.stack.setCurrentIndex(0)
            return

        self.stack.setCurrentIndex(1)
        self._loading_fields = True
        self.name_edit.setText(template.name)
        self.description_edit.setPlainText(template.description or "")
        self._set_code_preview(template)
        self._loading_fields = False

    def _set_code_preview(self, template: Template) -> None:
        path = template.code_file_path()
        if not path.exists():
            self.code_preview.setHtml(plain_message_to_preview_html("(файл code.py не найден)"))
            return
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.code_preview.setHtml(
                plain_message_to_preview_html(f"(не удалось прочитать code.py: {exc})")
            )
            return
        self.code_preview.setHtml(python_code_to_preview_html(source))

    def _on_name_editing_finished(self):
        if self._loading_fields or self.template is None:
            return

        new_name = self.name_edit.text().strip()
        if new_name == self.template.name:
            return

        old_name = self.template.name
        try:
            docs_with_old_name = [doc for doc in get_doc_manager().iterate() if doc.doc_class == old_name]
            self.temp_manager.rename(self.template, new_name)
            for doc in docs_with_old_name:
                doc.doc_class = new_name
                doc.template = self.template
                get_doc_manager().save_metadata(doc)
            self.template_name_changed.emit()
        except Exception as exc:
            show_warning_dialog(self, str(exc), "Ошибка переименования шаблона")
            self.name_edit.setText(self.template.name)

    def _on_description_changed(self):
        if self._loading_fields or self.template is None:
            return
        self._desc_timer.start(400)

    def _flush_description(self):
        if self.template is None:
            return
        text = self.description_edit.toPlainText().strip()
        self.template.description = text if text else None
        self.temp_manager.save_metadata(self.template)

    def _on_edit_code(self):
        if self.template is None:
            return
        path = self.template.code_file_path()
        if not path.exists():
            show_warning_dialog(self, "Файл code.py не найден.", "Ошибка редактирования шаблона")
            return
        _open_template_code_in_editor(path)

    def _on_delete_template(self):
        if self.template is None:
            return
        reply = QMessageBox.question(
            self,
            "Удаление шаблона",
            f"Удалить шаблон «{self.template.name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        t = self.template
        self.temp_manager.delete(t)
        self.template = None
        self.stack.setCurrentIndex(0)
        self.template_deleted.emit()
