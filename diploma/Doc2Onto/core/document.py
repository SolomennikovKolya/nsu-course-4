from dataclasses import dataclass, field
from contextlib import contextmanager
from typing import Optional
from pathlib import Path
from enum import StrEnum, auto

from app.context import get_temp_manager
from core.template.template import TemplateContext
from core.uddm.model import UDDM


@dataclass
class Document:
    """
    Легковесная модель документа в системе (Data Transfer Object).
    Не хранит в себе промежуточные данные обработки (UDDM, полный текст, триплеты и т.д.).
    """

    class Status(StrEnum):
        """Статусы обработки документа по ходу прохождения пайплайна."""

        UPLOADED = auto()          # Документ загружен в систему
        UDDM_EXTRACTED = auto()    # Построен UDDM
        CLASS_DETERMINED = auto()  # Определен класс документа
        FIELDS_EXTRACTED = auto()  # Извлечены поля (индивидуумы + литералы)
        FIELDS_VALIDATED = auto()  # Поля провалидированы
        TRIPLES_BUILT = auto()     # Построены триплеты
        ADDED_TO_MODEL = auto()    # Знания добавлены в онтологию

        def __int__(self):
            stages = {
                Document.Status.UPLOADED: 0,
                Document.Status.UDDM_EXTRACTED: 1,
                Document.Status.CLASS_DETERMINED: 2,
                Document.Status.FIELDS_EXTRACTED: 3,
                Document.Status.FIELDS_VALIDATED: 4,
                Document.Status.TRIPLES_BUILT: 5,
                Document.Status.ADDED_TO_MODEL: 6,
            }
            return stages[self]

    name: str                         # Название документа (имя оригинального файла)
    directory: Path                   # Директория с документом и его данными
    status: Status = Status.UPLOADED  # Статус обработки документа
    doc_class: Optional[str] = None   # Класс документа (название шаблона)

    pipeline_failed_target: Optional[Status] = None  # Статус шага, на котором пайплайн остановился с ошибкой
    pipeline_error_message: Optional[str] = None     # Сообщение об ошибке пайплайна

    # --- пути до промежуточных данных ---

    def original_file_path(self):
        return self.directory / self.name

    def uddm_file_path(self):
        return self.directory / "uddm.xml"

    def plain_text_file_path(self):
        return self.directory / "plain_text.txt"

    def uddm_html_view_file_path(self):
        return self.directory / "uddm_html_view.html"

    def uddm_tree_view_file_path(self):
        return self.directory / "uddm_tree_view.txt"

    def extraction_result_file_path(self):
        return self.directory / "extraction_result.json"

    def validation_result_file_path(self):
        return self.directory / "validation_result.json"

    def draft_graph_file_path(self):
        return self.directory / "draft_graph.json"

    def rdf_file_path(self):
        return self.directory / "rdf.ttl"


class DocumentContext:
    """
    Контекст документа, предоставляющий доступ к тяжеловесным данным.
    Используется для оптимальной работы с документами в рамках пайплайна.

    Принцип работы:
    - При первом обращении к данным, они загружаются из соответствующего файла.
    - При последующих обращениях к данным, они берутся из кеша.
    - Данные можно перезаписать путём обычным присваиванием.
    - Данные можно удалить путём вызова метода unload().
    """

    def __init__(self, doc: Document):
        self.document: Document = doc                         # DTO документа
        self._uddm: Optional[UDDM] = None                     # UDDM документа
        self._template_ctx: Optional[TemplateContext] = None  # Вложенный контекст шаблона

    @property
    def uddm(self) -> Optional[UDDM]:
        if self._uddm is not None:
            return self._uddm
        try:
            self._uddm = UDDM.load(self.document.uddm_file_path())
            return self._uddm
        except Exception as exc:
            return None

    @uddm.setter
    def uddm(self, uddm: Optional[UDDM]):
        self._uddm = uddm

    @property
    def template_ctx(self) -> Optional[TemplateContext]:
        if self._template_ctx:
            return self._template_ctx

        if self.document.doc_class is None:
            return None

        temp = get_temp_manager().get(self.document.doc_class)
        if temp is None:
            return None

        self._template_ctx = TemplateContext(temp)
        return self._template_ctx

    @template_ctx.setter
    def template_ctx(self, template_ctx: Optional[TemplateContext]):
        self._template_ctx = template_ctx

    def unload(self):
        self._uddm = None
        if self._template_ctx:
            self._template_ctx.unload()
            self._template_ctx = None


@contextmanager
def document_context(doc: Document):
    """
    Менеджер контекста документа. По сути это единая точка доступа ко всему runtime-состоянию.
    Используется в связке с ``with`` для автоматического освобождения ресурсов.

    Структура зависимостей:
    DocumentContext
        ├── document
        ├── uddm
        └── template_ctx
                ├── template
                ├── code
                └── fields
    """
    ctx = DocumentContext(doc)
    try:
        yield ctx
    finally:
        ctx.unload()
