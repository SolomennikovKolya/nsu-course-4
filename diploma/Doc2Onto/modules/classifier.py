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
                self.log(INFO, f'Документ уже классифицирован как "{temp.name}"')
                return ModuleResult.ok()

            self.log(WARNING, f'Несоответствие: документ имеет идентификатор шаблона "{doc.doc_class}" но шаблон не найден')

        # Автоматическая классификация
        uddm = ctx.uddm
        if not uddm:
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
                    self.log(INFO, f'Документ классифицирован как "{temp.name}"')
                    return ModuleResult.ok()
            except Exception:
                continue

        return ModuleResult.failed(message="Не удалось классифицировать документ")
