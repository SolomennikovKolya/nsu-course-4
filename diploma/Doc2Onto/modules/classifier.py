from logging import WARNING, INFO

from app.context import get_temp_manager
from modules.base import BaseModule, ModuleResult
from models.document import DocumentContext
from models.template import TemplateContext


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
                temp = ctx.template_ctx.template
                self.log(INFO, f'Document already classified as "{temp.name}"')
                return ModuleResult.ok()

            self.log(WARNING, f'Inconsistency: document has template id "{doc.doc_class}" but no template found')

        # Автоматическая классификация
        uddm = ctx.uddm
        if not uddm:
            self.log(WARNING, "Cannot classify document without UDDM")
            return ModuleResult.failed(message="Автоматическая классификация невозможна без UDDM")

        for temp in self.temp_manager.list():
            tctx = TemplateContext(temp)
            code = tctx.code
            if not code:
                continue

            try:
                if code.classify(doc.name, uddm):
                    doc.doc_class = temp.id
                    ctx.template_ctx = tctx
                    self.log(INFO, f'Document classified as "{temp.name}"')
                    return ModuleResult.ok()
            except Exception:
                continue

        self.log(WARNING, f"No template found to classify document")
        return ModuleResult.failed(message="Не удалось классифицировать документ")
