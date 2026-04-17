from logging import WARNING, INFO

from app.context import get_temp_manager
from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.uddm.model import UDDM


class Classifier(BaseModule):
    """Определение класса документа (шаблона)."""

    def __init__(self):
        super().__init__()
        self.temp_manager = get_temp_manager()

    def execute(self, document: Document) -> ModuleResult:
        try:
            # Если класс уже определён, надо только подгрузить шаблон
            if document.doc_class:
                if document.template:
                    self.log(INFO, f'Document already classified as "{document.doc_class}"')
                    return ModuleResult.OK

                template = self.temp_manager.get(document.doc_class)
                if template:
                    document.template = template
                    self.log(INFO, f'Document already classified as "{document.doc_class}"')
                    return ModuleResult.OK
                else:
                    self.log(WARNING, f'Inconsistency: document has class "{document.doc_class}" but no template found')

            # Автоматическая классификация
            uddm = UDDM.load(document.uddm_file_path())
            if not uddm:
                self.log(WARNING, "Cannot classify document without UDDM")
                return ModuleResult.FAILED

            for template_name in self.temp_manager.doc_classes_list():
                template = self.temp_manager.get(template_name)
                if not template or not template.code:
                    continue

                try:
                    if template.code.classify(document.name, uddm):
                        document.doc_class = template.name
                        document.template = template
                        self.log(INFO, f'Document classified as "{document.doc_class}"')
                        return ModuleResult.OK
                except Exception:
                    continue

            self.log(WARNING, f"No template found to classify document")
            return ModuleResult.FAILED

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED
