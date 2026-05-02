from logging import WARNING

from models.document import DocumentContext
from modules.base import BaseModule, ModuleResult
from core.graph.template_graph_builder import TemplateGraphBuilder
from modules.extractor import ExtractionResult


class GraphBuilder(BaseModule):
    """Построение графа RDF."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        tctx = ctx.template_ctx
        if not tctx:
            self.log(WARNING, f'Template "{doc.doc_class}" not found')
            return ModuleResult.failed(message=f"Не удалось загрузить шаблон")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            self.log(WARNING, f'Template "{tctx.template.name}" has no fields')
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        try:
            extr_res = ExtractionResult.load(doc.extraction_result_file_path())
        except Exception:
            self.log(WARNING, "Failed to load extraction result", exc_info=True)
            return ModuleResult.failed(message="Не удалось загрузить результат извлечения")

        field_values = {field.name: extr_res.get_value_final(field.name) for field in fields}
        builder = TemplateGraphBuilder(field_values)

        try:
            tctx.code.build(builder)
        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))

        builder._get_draft_graph().save(ctx.document.draft_graph_file_path())

        if doc.draft_graph_edits_file_path().exists():
            doc.draft_graph_edits_file_path().unlink()
        if doc.supplementary_facts_ttl_path().exists():
            doc.supplementary_facts_ttl_path().unlink()

        return ModuleResult.ok()
