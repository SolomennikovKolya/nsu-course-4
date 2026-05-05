from dataclasses import dataclass
from contextlib import contextmanager
from typing import Optional
from pathlib import Path
from enum import StrEnum, auto

from app.context import get_temp_manager
from app.settings import ORIGINAL_FILE_STEM
from core.graph.draft_graph import DraftGraph
from core.uddm.model import UDDM
from models.template import TemplateContext
from models.extraction_result import ExtractionResult
from models.validation_result import ValidationResult


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

    id: str                           # Уникальный идентификатор документа в системе (имя каталога хранения)
    original_suffix: str              # Расширение исходного файла (файл: original + suffix в каталоге id)
    directory: Path                   # Директория с документом и его данными
    name: str                         # Название документа (храится только в мета-файле, используется в UI)

    status: Status = Status.UPLOADED  # Статус обработки документа
    doc_class: Optional[str] = None   # Класс документа (ID шаблона)

    pipeline_failed_target: Optional[Status] = None  # Статус шага, на котором пайплайн остановился с ошибкой
    pipeline_error_message: Optional[str] = None     # Сообщение об ошибке пайплайна

    # --- пути до промежуточных данных ---

    def original_file_path(self) -> Path:
        return self.directory / f"{ORIGINAL_FILE_STEM}{self.original_suffix}"

    def uddm_file_path(self) -> Path:
        return self.directory / "uddm.xml"

    def plain_text_file_path(self) -> Path:
        return self.directory / "plain_text.txt"

    def uddm_html_view_file_path(self) -> Path:
        return self.directory / "uddm_html_view.html"

    def uddm_tree_view_file_path(self) -> Path:
        return self.directory / "uddm_tree_view.txt"

    def extraction_result_file_path(self) -> Path:
        return self.directory / "extraction_result.json"

    def validation_result_file_path(self) -> Path:
        return self.directory / "validation_result.json"

    def draft_graph_file_path(self) -> Path:
        return self.directory / "draft_graph.json"

    def draft_graph_edits_file_path(self) -> Path:
        return self.directory / "draft_graph_edits.json"

    def supplementary_facts_ttl_path(self) -> Path:
        return self.directory / "supplementary_facts.ttl"

    def final_graph_file_path(self) -> Path:
        return self.directory / "final_graph.ttl"

    def ontology_merge_report_file_path(self) -> Path:
        """Отчёт о перезаписи фактов при слиянии с моделью (для UI)."""
        return self.directory / "ontology_merge_report.json"


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
        self._extr_res: Optional[ExtractionResult] = None     # Результат извлечения полей
        self._val_res: Optional[ValidationResult] = None      # Результат валидации полей
        self._draft_graph: Optional[DraftGraph] = None        # Черновой граф
        self._template_ctx: Optional[TemplateContext] = None  # Вложенный контекст шаблона

    @property
    def uddm(self) -> Optional[UDDM]:
        if self._uddm is not None:
            return self._uddm
        try:
            self._uddm = UDDM.load(self.document.uddm_file_path())
            return self._uddm
        except Exception:
            return None

    @uddm.setter
    def uddm(self, uddm: Optional[UDDM]):
        self._uddm = uddm

    @property
    def extraction_result(self) -> Optional[ExtractionResult]:
        if self._extr_res is not None:
            return self._extr_res
        try:
            self._extr_res = ExtractionResult.load(self.document.extraction_result_file_path())
            return self._extr_res
        except Exception:
            return None

    @extraction_result.setter
    def extraction_result(self, extraction_result: Optional[ExtractionResult]):
        self._extr_res = extraction_result

    @property
    def validation_result(self) -> Optional[ValidationResult]:
        if self._val_res is not None:
            return self._val_res
        try:
            self._val_res = ValidationResult.load(self.document.validation_result_file_path())
            return self._val_res
        except Exception:
            return None

    @validation_result.setter
    def validation_result(self, validation_result: Optional[ValidationResult]):
        self._val_res = validation_result

    @property
    def draft_graph(self) -> Optional[DraftGraph]:
        if self._draft_graph is not None:
            return self._draft_graph
        try:
            self._draft_graph = DraftGraph.load(self.document.draft_graph_file_path())
            return self._draft_graph
        except Exception:
            return None

    @draft_graph.setter
    def draft_graph(self, draft_graph: Optional[DraftGraph]):
        self._draft_graph = draft_graph

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
        self._extr_res = None
        self._val_res = None
        self._draft_graph = None
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
        ├── extraction_result
        ├── validation_result
        ├── draft_graph
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
