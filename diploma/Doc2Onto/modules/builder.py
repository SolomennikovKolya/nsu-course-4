from typing import List, Dict
from logging import WARNING, INFO
from typing import Optional

from core.document import Document, DocumentContext
from modules.base import BaseModule, ModuleResult
from modules.validator import ValidationResult
from core.template.field import Field
from core.graph.template_graph_builder import TemplateGraphBuilder


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

        code = tctx.code
        if not code:
            self.log(WARNING, f'Template "{tctx.template.name}" has no code')
            return ModuleResult.failed(message=f"Шаблон не имеет кода")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            self.log(WARNING, f'Template "{tctx.template.name}" has no fields')
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        valid_res = ValidationResult.load(doc.validation_result_file_path())
        if not self._check_field_names_consistency(fields, valid_res):
            self.log(WARNING, f'Field names consistency check failed for template "{tctx.template.name}"')
            msg = "Неконсистентность структур: набор полей после валидации и в шаблоне не совпадает. Перезапустите обработку"
            return ModuleResult.failed(message=msg)

        field_values = self._validation_res_to_values(valid_res)
        if not all(v is not None for v in field_values.values()):
            self.log(WARNING, "Not all field values are present")
            return ModuleResult.failed(message="Не все значения полей распознаны")

        builder = TemplateGraphBuilder(field_values)
        try:
            tctx.code.build(builder)
        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))

        builder._get_draft_graph().serialize(ctx.document.draft_graph_file_path())
        return ModuleResult.ok()

    def _validation_res_to_values(self, valid_res: ValidationResult) -> Dict[str, Optional[str]]:
        values = dict()
        for field_name in valid_res.fields.keys():
            values[field_name] = (
                valid_res.get_corrected_value_manual(field_name)
                or valid_res.get_corrected_value_llm(field_name)
                or valid_res.get_extracted_value(field_name)
            )
        return values

    def _check_field_names_consistency(self, fields: List[Field], validation_res: ValidationResult) -> bool:
        template_names = [field.name for field in fields]
        validation_names = list(validation_res.fields.keys())
        return set(template_names) == set(validation_names)
