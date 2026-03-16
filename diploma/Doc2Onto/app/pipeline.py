from dataclasses import dataclass
from enum import Enum

from core.document.document import Document
from core.document.status import DocumentStatus
from app.modules.base import BaseModule, ModuleResult
from app.modules.converter.converter import Converter


@dataclass
class PipelineStage:
    """Описание стадии пайплайна."""

    name: str
    target_status: DocumentStatus
    module: BaseModule


class PipelineResult(str, Enum):
    """Результат выполнения пайплайна."""

    OK = "ok"
    FAILED = "failed"

    def __str__(self):
        return self.value

    def __int__(self):
        return int(self.value == PipelineResult.OK)


class PipelineEngine:

    def __init__(self):
        self.stages = [
            PipelineStage(
                name="conversion",
                target_status=DocumentStatus.UDDM_EXTRACTED,
                module=Converter()
            ),
            # PipelineStage(
            #     name="classification",
            #     target_status=DocumentStatus.CLASS_DETERMINED,
            #     module=Classifier()
            # ),
            # PipelineStage(
            #     name="extraction",
            #     target_status=DocumentStatus.KNOWLEDGE_EXTRACTED,
            #     module=Extractor()
            # ),
            # PipelineStage(
            #     name="validation",
            #     target_status=DocumentStatus.VALIDATED,
            #     module=Validator()
            # ),
            # PipelineStage(
            #     name="model_insertion",
            #     target_status=DocumentStatus.ADDED_TO_MODEL,
            #     module=ModelInsertor()
            # ),
        ]

    def run(self, document: Document, final_stage: DocumentStatus = DocumentStatus.ADDED_TO_MODEL) -> PipelineResult:
        """Начинает / продолжает обработку докумнта до достижения final_stage."""
        for stage in self.stages:

            # Если стадия уже выполнена — пропускаем
            if int(document.status) >= int(stage.target_status):
                continue

            result = stage.module.execute(document)
            if result != ModuleResult.OK:
                break

            if document.status == final_stage:
                break

        return PipelineResult.OK if int(document.status) >= int(final_stage) else PipelineResult.FAILED
