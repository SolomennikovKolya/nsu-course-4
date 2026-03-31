from logging import WARNING

from app.context import get_temp_manager
from modules.base import BaseModule, ModuleResult
from core.document import Document


class Classifier(BaseModule):
    """Определение класса документа (шаблона)."""

    def __init__(self):
        super().__init__()
        self.temp_manager = get_temp_manager()

    def execute(self, document: Document) -> ModuleResult:
        try:
            # Если класс уже определён
            if document.doc_class:
                if document.template:
                    return ModuleResult.OK

                template = self.temp_manager.get(document.doc_class)
                if template:
                    document.template = template
                    return ModuleResult.OK
                else:
                    self.log(WARNING, f"Inconsistency found: document has class {document.doc_class} but no template found")

            # Автоматическая классификация
            for template_name in self.temp_manager.doc_classes_list():
                template = self.temp_manager.get(template_name)
                if not template or not template.code:
                    continue

                try:
                    if template.code.classify(document):
                        document.doc_class = template.name
                        document.template = template
                        return ModuleResult.OK
                except Exception:
                    continue

            return ModuleResult.FAILED

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED
