from models.document import DocumentContext
from modules.base import BaseModule, ModuleResult
from core.graph.template_graph_builder import TemplateGraphBuilder


class GraphBuilder(BaseModule):
    """Построение графа RDF."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        tctx = ctx.template_ctx
        if not tctx:
            return ModuleResult.failed(message=f"Не удалось загрузить шаблон")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        extr_res = ctx.extraction_result
        if not extr_res:
            return ModuleResult.failed(message="Не удалось загрузить результат извлечения")

        field_values = {field.name: extr_res.get_value_final(field.name) for field in fields}
        builder = TemplateGraphBuilder(field_values)

        try:
            tctx.code.build(builder)
        except Exception as ex:
            return ModuleResult.failed(message=f"Ошибка построения графа RDF: {ex}")

        ctx.draft_graph = builder._get_draft_graph()
        ctx.draft_graph.save(doc.draft_graph_file_path())

        # Удаляем неактуальные файлы ручных правок
        if doc.draft_graph_edits_file_path().exists():
            doc.draft_graph_edits_file_path().unlink()
        if doc.supplementary_facts_ttl_path().exists():
            doc.supplementary_facts_ttl_path().unlink()

        return ModuleResult.ok()
