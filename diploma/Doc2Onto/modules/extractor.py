from app.context import get_temp_manager
from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.template.template import Template
from core.uddm import UDDM
from core.template.base import ExtractionResult


class Extractor(BaseModule):
    """Извлечение RDF-термов (индивидуумы + литералы)."""

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

            uddm = UDDM.load(document.uddm_file_path())

            extraction_result = self._extract(template, uddm)

            self._save_extraction(document, extraction_result)

            document.status = Document.Status.TERMS_EXTRACTED
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _extract(self, template: Template, uddm: UDDM) -> ExtractionResult:
        result = ExtractionResult()

        # TODO: дописать логику
        # for field in template.fields():
        #     try:
        #         value = field.selector.apply(uddm)
        #         value = field.extractor.apply(value)

        #         result.add(field, value)

        #     except Exception:
        #         result.add(field, None)

        return result

    def _save_extraction(self, document: Document, result: ExtractionResult):
        # TODO: сохранить в JSON
        document.directory.joinpath("extraction.json")
