from logging import WARNING, INFO

from app.context import get_temp_manager
from modules.base import BaseModule, ModuleResult
from core.document import DocumentContext
from core.template.template import TemplateContext


class Classifier(BaseModule):
    """Определение класса документа (шаблона)."""

    def __init__(self):
        super().__init__()
        self.temp_manager = get_temp_manager()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        # Если класс уже определён и шаблон доступен — повторная классификация не нужна
        if doc.doc_class:
            if ctx.template_ctx:
                self.log(INFO, f'Document already classified as "{doc.doc_class}"')
                return ModuleResult.ok()

            self.log(WARNING, f'Inconsistency: document has class "{doc.doc_class}" but no template found')

        # Автоматическая классификация
        uddm = ctx.uddm
        if not uddm:
            self.log(WARNING, "Cannot classify document without UDDM")
            return ModuleResult.failed(message="Автоматическая классификация невозможна без UDDM")

        for temp_name in self.temp_manager.doc_classes_list():
            temp = self.temp_manager.get(temp_name)
            if not temp:
                continue

            tctx = TemplateContext(temp)
            code = tctx.code
            if not code:
                continue

            try:
                if code.classify(doc.name, uddm):
                    doc.doc_class = temp_name
                    ctx.template_ctx = tctx
                    self.log(INFO, f'Document classified as "{doc.doc_class}"')
                    return ModuleResult.ok()
            except Exception:
                continue

        self.log(WARNING, f"No template found to classify document")
        return ModuleResult.failed(message="Не удалось классифицировать документ")
