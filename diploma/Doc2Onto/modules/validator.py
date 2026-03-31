from app.context import get_temp_manager
from core.document import Document
from core.template.base import ExtractionResult
from core.template.field_validator import ValidationResult
from modules.base import BaseModule, ModuleResult


class Validator(BaseModule):
    """Валидация извлечённых RDF-термов."""

    def __init__(self):
        super().__init__()
        self.temp_manager = get_temp_manager()

    def execute(self, document: Document) -> ModuleResult:
        try:
            raise NotImplementedError()
            if not document.doc_class:
                return ModuleResult.FAILED

            template = self.temp_manager.get(document.doc_class)
            if not template:
                return ModuleResult.FAILED

            extraction = self._load_extraction(document)

            # TODO: реальная валидация
            # validation_result = template.validate(extraction)
            validation_result = ValidationResult()

            self._save_validation(document, validation_result)

            document.status = Document.Status.TERMS_VALIDATED
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _load_extraction(self, document: Document):
        # TODO
        return ExtractionResult()

    def _save_validation(self, document: Document, validation_result):
        # TODO
        document.directory.joinpath("validated.json")
