from app.context import get_temp_manager
from core.document import Document
from modules.base import BaseModule, ModuleResult


class TripleBuilder(BaseModule):
    """Построение RDF-триплетов."""

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

            validation = self._load_validation(document)

            # TODO: реальное построение триплетов
            # triples = template.build_triples(validation)
            triples = None

            self._save_triples(document, triples)

            document.status = Document.Status.TRIPLES_BUILT
            return ModuleResult.OK

        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))

    def _load_validation(self, document: Document):
        # TODO
        return None

    def _save_triples(self, document: Document, triples):
        # TODO: сохранить RDF (ttl/jsonld)
        pass
