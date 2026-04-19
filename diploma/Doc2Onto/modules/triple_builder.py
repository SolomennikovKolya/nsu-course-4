from core.document import Document, DocumentContext
from modules.base import BaseModule, ModuleResult


class TripleBuilder(BaseModule):
    """Построение RDF-триплетов."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        document = ctx.document
        try:
            raise NotImplementedError("Модуль не реализован")
            if not document.doc_class or ctx.template_ctx is None:
                return ModuleResult.failed(message="Шаблон не найден")

            validation = self._load_validation(document)

            # TODO: реальное построение триплетов (ctx.template_ctx.code.build_triples(...))
            triples = None

            self._save_triples(document, triples)

            return ModuleResult.ok()

        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))

    def _load_validation(self, document: Document):
        # TODO
        return None

    def _save_triples(self, document: Document, triples):
        # TODO: сохранить RDF (ttl/jsonld), например document.rdf_file_path()
        pass
