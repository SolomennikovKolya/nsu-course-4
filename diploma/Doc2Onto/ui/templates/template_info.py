import shutil
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import get_doc_manager, get_pipeline, get_temp_manager
from app.openai import ask_gpt, read_prompt
from app.settings import (
    PROJECT_ROOT, APP_NAME,
    GENERATE_DESCR_SYS_PROMPT_PATH,
    GENERATE_DESCR_USER_PROMPT_PATH,
    GENERATE_TEMP_SYS_PROMPT_PATH,
    GENERATE_TEMP_USER_PROMPT_PATH,
    TEMPLATE_CODE_EXAMPLE_PATH,
)
from app.utils import require_attribute
from core.document import Document
from core.template.template import Template
from infrastructure.storage.template_loader import TemplateLoader
from ui.common.editable_title import EditableTitleWidget
from ui.templates.python_code_html import plain_message_to_preview_html, python_code_to_preview_html


def require_template(method):
    """Проверяет наличие шаблона перед выполнением метода."""
    return require_attribute("template")(method)


def _open_template_code_in_editor(code_path: Path) -> None:
    """
    Открывает code.py в VS Code / Cursor с корнем проекта как workspace — иначе Pylance не видит импорты (core, app, …).

    Вызываем ``code . <относительный_путь>`` с ``cwd`` = корень проекта; при несовпадении дисков — ``code <root> <file>``.
    """
    root = PROJECT_ROOT
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
        empty_layout = QVBoxLayout(page)

        empty_label = QLabel("Выберите шаблон")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(empty_label)
        empty_layout.addStretch()
        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # --- Заголовок ---
        self.title = EditableTitleWidget(
            placeholder="Название шаблона",
            title_style="font-size:16px;font-weight:bold;",
            subdued_style="color:#8a8a8a;",
        )
        self.title.committed.connect(self._on_template_name_committed)
        page_layout.addWidget(self.title)

        # --- Описание ---
        description_widget = QWidget()
        description_layout = QVBoxLayout(description_widget)
        description_layout.setContentsMargins(0, 0, 0, 0)

        self.description_stack = QStackedWidget()

        self.description_view = QTextBrowser()
        self.description_view.setOpenExternalLinks(True)
        self.description_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Краткое описание шаблона…")
        self.description_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.description_edit.textChanged.connect(self._on_description_changed)
        self.description_stack.addWidget(self.description_view)
        self.description_stack.addWidget(self.description_edit)
        self.description_stack.setCurrentWidget(self.description_view)

        description_actions = QHBoxLayout()
        self.toggle_description_mode_btn = QPushButton("Редактировать описание")
        self.toggle_description_mode_btn.clicked.connect(self._on_toggle_description_mode)
        description_actions.addWidget(self.toggle_description_mode_btn)

        self.generate_description_btn = QPushButton("Сгенерировать описание")
        self.generate_description_btn.setToolTip(
            "Сгенерировать лаконичное описание на основе выбранного примера документа"
        )
        self.generate_description_btn.clicked.connect(self._on_generate_description)
        description_actions.addWidget(self.generate_description_btn)
        description_actions.addStretch()

        description_layout.addWidget(self.description_stack, 1)
        description_layout.addLayout(description_actions)
        description_layout.addSpacing(6)

        # --- Предпросмотр кода шаблона и кнопки действий---
        code_preview_widget = QWidget()
        code_preview_layout = QVBoxLayout(code_preview_widget)
        code_preview_layout.setContentsMargins(0, 0, 0, 0)
        code_preview_layout.addSpacing(6)
        code_preview_layout.addWidget(QLabel("Предпросмотр кода:"))
        self.code_preview = QTextBrowser()
        self.code_preview.setReadOnly(True)
        self.code_preview.setOpenExternalLinks(False)
        code_preview_layout.addWidget(self.code_preview, 1)

        actions_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Редактировать шаблон")
        self.edit_btn.setToolTip("Открыть code.py в VS Code (если доступен командой code), иначе в редакторе по умолчанию")
        self.edit_btn.clicked.connect(self._on_edit_code)

        self.generate_template_btn = QPushButton("Сгенерировать шаблон")
        self.generate_template_btn.setToolTip("Сгенерировать code.py на основе описания и примера UDDM")
        self.generate_template_btn.clicked.connect(self._on_generate_template_code)

        self.validate_btn = QPushButton("Валидировать шаблон")
        self.validate_btn.setToolTip("Проверка синтаксиса и структуры класса TemplateCode")
        self.validate_btn.clicked.connect(self._on_validate_template)

        self.delete_btn = QPushButton("Удалить шаблон")
        self.delete_btn.setMaximumWidth(140)
        self.delete_btn.setStyleSheet("""
        QPushButton:hover {
            background-color: #d32f2f;
            color: white;
        }
        """)
        self.delete_btn.clicked.connect(self._on_delete_template)

        actions_layout.addWidget(self.edit_btn)
        actions_layout.addWidget(self.generate_template_btn)
        actions_layout.addWidget(self.validate_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.delete_btn)
        code_preview_layout.addLayout(actions_layout)

        # --- Сплиттер между описанием и предпросмотром ---
        self.details_splitter = QSplitter(Qt.Orientation.Vertical)
        self.details_splitter.addWidget(description_widget)
        self.details_splitter.addWidget(code_preview_widget)
        self.details_splitter.setChildrenCollapsible(True)
        self.details_splitter.setStretchFactor(0, 1)
        self.details_splitter.setStretchFactor(1, 2)
        self.details_splitter.setSizes([220, 480])
        page_layout.addWidget(self.details_splitter, 1)

        return page

    @require_template
    def current_template_name(self, template: Template) -> Optional[str]:
        return template.name

    def set_template(self, template: Optional[Template]):
        self.template = template
        if template is None:
            self.stack.setCurrentIndex(0)
            return

        self.stack.setCurrentIndex(1)
        self._loading_fields = True
        self.title.set_value(template.name)
        description = template.description or ""
        self.description_edit.setPlainText(description)
        self._render_description_markdown(description)
        self._set_description_edit_mode(False)
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
            self.code_preview.setHtml(plain_message_to_preview_html(f"(не удалось прочитать code.py: {exc})"))
            return
        self.code_preview.setHtml(python_code_to_preview_html(source))

    def _on_template_name_committed(self, new_name: str):
        if self._loading_fields or self.template is None:
            return

        new_name = (new_name or "").strip()
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
            QMessageBox.warning(self, APP_NAME, str(exc))
            self.title.set_value(self.template.name)

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
        self._render_description_markdown(text)

    def _render_description_markdown(self, text: str) -> None:
        if text.strip():
            self.description_view.setMarkdown(text)
            return
        self.description_view.setHtml("<i>Описание отсутствует.</i>")

    def _set_description_edit_mode(self, is_edit_mode: bool) -> None:
        if is_edit_mode:
            self.description_stack.setCurrentWidget(self.description_edit)
            self.toggle_description_mode_btn.setText("Завершить редактирование")
            return
        self.description_stack.setCurrentWidget(self.description_view)
        self.toggle_description_mode_btn.setText("Редактировать описание")

    def _on_toggle_description_mode(self) -> None:
        is_edit_mode = self.description_stack.currentWidget() is self.description_edit
        if is_edit_mode:
            self._flush_description()
            self._set_description_edit_mode(False)
            return
        self._set_description_edit_mode(True)

    def _choose_example_document(self) -> Optional[Document]:
        """Выбирает пример документа с UDDM-представлением."""
        docs = [doc for doc in get_doc_manager().iterate() if doc.uddm_tree_view_file_path().exists()]
        if not docs:
            QMessageBox.warning(
                self, APP_NAME,
                "Нет документов с UDDM-представлением. Сначала загрузите и обработайте документ до этапа UDDM."
            )
            return None

        docs.sort(key=lambda d: d.name.lower())
        names = [d.name for d in docs]

        selected_name, ok = QInputDialog.getItem(
            self, APP_NAME,
            "Выберите пример документа:",
            names, 0, False
        )
        if not ok or not selected_name:
            return None

        for doc in docs:
            if doc.name == selected_name:
                return doc
        return None

    def _choose_optional_unfilled_document_text(self) -> str:
        """
        Опционально выбирает внешний (незаполненный) документ и извлекает для него UDDM tree view.

        Документ обрабатывается во временной директории до стадии UDDM_EXTRACTED и не добавляется в систему.
        """
        reply = QMessageBox.question(
            self,
            APP_NAME,
            "Добавить незаполненный документ как дополнительный пример для генерации описания?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите незаполненный документ",
            str(PROJECT_ROOT),
            "Документы (*.pdf *.doc *.docx *.txt *.rtf *.odt *.xlsx *.xls);;Все файлы (*)",
        )
        if not file_path:
            return ""

        source_path = Path(file_path)
        if not source_path.exists():
            QMessageBox.warning(self, APP_NAME, "Выбранный файл не найден.")
            return ""

        pipeline = get_pipeline()
        with tempfile.TemporaryDirectory(prefix="doc2onto_unfilled_") as tmp_dir:
            temp_dir = Path(tmp_dir)
            temp_file_path = temp_dir / source_path.name
            shutil.copy2(source_path, temp_file_path)

            temp_doc = Document(name=source_path.name, directory=temp_dir)
            result = pipeline.run(temp_doc, Document.Status.UDDM_EXTRACTED)
            if int(temp_doc.status) < int(Document.Status.UDDM_EXTRACTED):
                QMessageBox.warning(
                    self,
                    APP_NAME,
                    f"Не удалось извлечь UDDM для выбранного файла (результат пайплайна: {result}).",
                )
                return ""

            tree_path = temp_doc.uddm_tree_view_file_path()
            if not tree_path.exists():
                QMessageBox.warning(self, APP_NAME, "UDDM tree view для выбранного файла не создан.")
                return ""

            try:
                return tree_path.read_text(encoding="utf-8", errors="strict")
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME, f"Не удалось прочитать UDDM tree view: {exc}")
                return ""

    @require_template
    def _on_generate_description(self, template: Template) -> None:
        example_doc = self._choose_example_document()
        if example_doc is None:
            return
        example_text = example_doc.uddm_tree_view_file_path().read_text(encoding="utf-8", errors="strict")
        # unfilled_document_text = self._choose_optional_unfilled_document_text()

        system_prompt = read_prompt(GENERATE_DESCR_SYS_PROMPT_PATH)
        user_prompt = read_prompt(
            GENERATE_DESCR_USER_PROMPT_PATH,
            template_name=template.name,
            document_example=example_text,
            # unfilled_document=unfilled_document_text,
        )

        self.generate_description_btn.setEnabled(False)
        try:
            description = ask_gpt(user_prompt, system_prompt=system_prompt)
            if not description:
                raise RuntimeError("Модель вернула пустое описание")

            template.description = description
            self.description_edit.setPlainText(description)
            self._flush_description()
            QMessageBox.information(self, APP_NAME, "Описание шаблона сгенерировано.")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сгенерировать описание: {e}")
        finally:
            self.generate_description_btn.setEnabled(True)

    @require_template
    def _on_generate_template_code(self, template: Template) -> None:
        description = (template.description or "").strip()
        if not description:
            QMessageBox.warning(self, APP_NAME, "Сначала заполните описание шаблона.")
            return

        example_doc = self._choose_example_document()
        if example_doc is None:
            return
        uddm_example = example_doc.uddm_tree_view_file_path().read_text(encoding="utf-8", errors="strict")

        try:
            code_example = TEMPLATE_CODE_EXAMPLE_PATH.read_text(encoding="utf-8", errors="strict")
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось прочитать шаблон кода-пример: {exc}")
            return

        system_prompt = read_prompt(GENERATE_TEMP_SYS_PROMPT_PATH)
        user_prompt = read_prompt(
            GENERATE_TEMP_USER_PROMPT_PATH,
            template_description=description,
            uddm_example=uddm_example,
            code_example=code_example,
        )

        self.generate_template_btn.setEnabled(False)
        try:
            generated_code = ask_gpt(user_prompt, system_prompt=system_prompt).strip()
            if not generated_code:
                raise RuntimeError("Модель вернула пустой код")

            code_path = template.code_file_path()
            code_path.write_text(generated_code + "\n", encoding="utf-8")
            template.code = TemplateLoader.load(template)

            self._set_code_preview(template)
            QMessageBox.information(self, APP_NAME, "Код шаблона успешно сгенерирован.")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сгенерировать код шаблона: {e}")
        finally:
            self.generate_template_btn.setEnabled(True)

    def _on_edit_code(self):
        if self.template is None:
            return
        path = self.template.code_file_path()
        if not path.exists():
            QMessageBox.warning(self, APP_NAME, "Ошибка редактирования шаблона: файл code.py не найден.")
            return
        _open_template_code_in_editor(path)

    def _on_validate_template(self) -> None:
        if self.template is None:
            return

        code = self.template.code
        if code is None:
            QMessageBox.warning(
                self,
                APP_NAME,
                "Код шаблона не загружен (ошибка при загрузке code.py). "
                "Исправьте файл и перезагрузите шаблоны или перезапустите приложение.",
            )
            return

        try:
            TemplateLoader.validate_code(code)
            QMessageBox.information(self, APP_NAME, "Шаблон успешно проверен.")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    def _on_delete_template(self):
        if self.template is None:
            return
        reply = QMessageBox.question(
            self,
            APP_NAME,
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
