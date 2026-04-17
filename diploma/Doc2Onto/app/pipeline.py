from dataclasses import dataclass
from typing import Optional, Self

from app.context import get_logger
from core.document import Document
from modules import Converter, Classifier, Extractor, Validator, TripleBuilder, Connector
from modules.base import BaseModule, ModuleResult


@dataclass(frozen=True)
class PipelineResult:
    """Результат выполнения пайплайна."""

    OK = "OK"
    FAILED = "FAILED"

    success: bool
    failed_status: Optional[Document.Status] = None

    @classmethod
    def ok(cls) -> Self:
        return cls(success=True)

    @classmethod
    def failed(cls, status: Optional[Document.Status] = None) -> Self:
        return cls(success=False, failed_status=status)

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
                name="triple_building",
                start_status=Document.Status.FIELDS_VALIDATED,
                target_status=Document.Status.TRIPLES_BUILT,
                module=TripleBuilder()
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

    def run(self, document: Document, final_stage: Document.Status = Document.Status.ADDED_TO_MODEL) -> PipelineResult:
        """Начинает / продолжает обработку докумнта до достижения final_stage."""
        if not self.setup_done:
            self.setup()

        self.logger.info(f"[Pipeline] started")
        self.logger.info(f'  Document: "{document.name}"')
        self.logger.info(f"  Target status: {document.status} -> {final_stage}")

        if int(document.status) >= int(final_stage):
            self.logger.info(f"[Pipeline] code: {PipelineResult.OK} (document already at status {document.status})")
            return PipelineResult.ok()

        for stage in self.stages:
            if document.status == stage.start_status:
                self.logger.info(f"  <{stage.name}> started")
                result = stage.module.execute(document)
                self.logger.info(f"  <{stage.name}> code: {result}")

                if result == ModuleResult.OK:
                    document.status = stage.target_status
                else:
                    document.failed_status = stage.target_status
                    self.logger.info(f"  Final status: {document.status}")
                    self.logger.info(f"[Pipeline] code: {PipelineResult.FAILED}")
                    return PipelineResult.failed(stage.target_status)

            if int(document.status) >= int(final_stage):
                break

        self.logger.info(f"  Final status: {document.status}")
        self.logger.info(f"[Pipeline] code: {PipelineResult.OK}")
        return PipelineResult.ok()
