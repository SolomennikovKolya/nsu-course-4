from dataclasses import dataclass
from typing import Optional, Self

from app.context import get_logger
from models.document import Document, DocumentContext, document_context
from modules import Converter, Classifier, Extractor, Validator, GraphBuilder, Connector
from modules.base import BaseModule, ModuleResult


@dataclass(frozen=True)
class PipelineResult:
    """Результат выполнения пайплайна."""

    OK = "OK"
    FAILED = "FAILED"

    success: bool
    message: Optional[str] = None
    failed_status: Optional[Document.Status] = None  # Статус, до которого не удалось дойти

    @classmethod
    def ok(cls, *, message: Optional[str] = None) -> Self:
        return cls(success=True, message=message)

    @classmethod
    def failed(cls, *, message: Optional[str] = None, failed_status: Optional[Document.Status] = None) -> Self:
        return cls(success=False, message=message, failed_status=failed_status)

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        return self.OK if self.success else self.FAILED


class Pipeline:

    @dataclass
    class Stage:
        name: str
        start_status: Document.Status
        target_status: Document.Status
        module: BaseModule

    def __init__(self):
        self.setup_done = False

    def setup(self):
        """
        Настройка пайплайна. Определение последовательности стадий обработки документа.
        Настройка выполняется не сразу при инициализации пайплайна, а при первом запуске, 
        чтобы избежать проблем с импортами.
        """
        self.stages = [
            Pipeline.Stage(
                name="conversion",
                start_status=Document.Status.UPLOADED,
                target_status=Document.Status.UDDM_EXTRACTED,
                module=Converter()
            ),
            Pipeline.Stage(
                name="classification",
                start_status=Document.Status.UDDM_EXTRACTED,
                target_status=Document.Status.CLASS_DETERMINED,
                module=Classifier()
            ),
            Pipeline.Stage(
                name="terms_extraction",
                start_status=Document.Status.CLASS_DETERMINED,
                target_status=Document.Status.FIELDS_EXTRACTED,
                module=Extractor()
            ),
            Pipeline.Stage(
                name="validation",
                start_status=Document.Status.FIELDS_EXTRACTED,
                target_status=Document.Status.FIELDS_VALIDATED,
                module=Validator()
            ),
            Pipeline.Stage(
                name="graph_building",
                start_status=Document.Status.FIELDS_VALIDATED,
                target_status=Document.Status.TRIPLES_BUILT,
                module=GraphBuilder()
            ),
            Pipeline.Stage(
                name="model_insertion",
                start_status=Document.Status.TRIPLES_BUILT,
                target_status=Document.Status.ADDED_TO_MODEL,
                module=Connector()
            ),
        ]

        self.logger = get_logger()

        self.setup_done = True

    def run(self, doc: Document, final_stage: Document.Status = Document.Status.ADDED_TO_MODEL) -> PipelineResult:
        """Начинает / продолжает обработку докумнта до достижения final_stage."""
        if not self.setup_done:
            self.setup()

        doc.pipeline_failed_target = None
        doc.pipeline_error_message = None

        self.logger.info(f"[Pipeline] started")
        self.logger.info(f'  Document: "{doc.name}" [id={doc.id}]')
        self.logger.info(f"  Target status: {doc.status} -> {final_stage}")

        if int(doc.status) >= int(final_stage):
            self.logger.info(f"[Pipeline] code: {PipelineResult.OK} (document already at status {doc.status})")
            return PipelineResult.ok()

        with document_context(doc) as ctx:
            return self._full_run(ctx, final_stage)

    def _full_run(self, ctx: DocumentContext, final_stage: Document.Status):
        for stage in self.stages:
            if ctx.document.status == stage.start_status:
                self.logger.info(f"  <{stage.name}> started")
                result = stage.module.execute(ctx)
                self.logger.info(f"  <{stage.name}> code: {result}")

                if bool(result):
                    ctx.document.status = stage.target_status
                else:
                    module_name = stage.module.__class__.__name__
                    err_msg = result.message or f"Ошибка выполнения модуля {module_name}"
                    ctx.document.pipeline_failed_target = stage.target_status
                    ctx.document.pipeline_error_message = err_msg
                    self.logger.warning(f"    [{module_name}] " + err_msg, exc_info=True)
                    self.logger.info(f"  Final status: {ctx.document.status}")
                    self.logger.info(f"[Pipeline] code: {PipelineResult.FAILED}")
                    return PipelineResult.failed(message=err_msg, failed_status=stage.target_status)

            if int(ctx.document.status) >= int(final_stage):
                break

        self.logger.info(f"  Final status: {ctx.document.status}")
        self.logger.info(f"[Pipeline] code: {PipelineResult.OK}")
        return PipelineResult.ok()
