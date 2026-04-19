from modules.base import BaseModule, ModuleResult
from core.document import Document, DocumentContext


class Connector(BaseModule):
    """Добавление триплетов в онтологическую модель."""

    def __init__(self):
        super().__init__()
        # TODO: подключение к RDF-хранилищу
        pass

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        document = ctx.document
        try:
            raise NotImplementedError("Модуль не реализован")
            triples = self._load_triples(document)

            # TODO: вставка в graph (rdflib / triplestore)

            return ModuleResult.ok()

        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))

    def _load_triples(self, document: Document):
        # TODO: загрузка из document.rdf_file_path()
        return []
