import logging

from modules.base import BaseModule, ModuleResult
from core.document import Document


class Connector(BaseModule):
    """Добавление триплетов в онтологическую модель."""

    def __init__(self):
        super().__init__()
        # TODO: подключение к RDF-хранилищу
        pass

    def execute(self, document: Document) -> ModuleResult:
        try:
            raise NotImplementedError()
            triples = self._load_triples(document)

            # TODO: вставка в graph (rdflib / triplestore)

            document.status = Document.Status.ADDED_TO_MODEL
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _load_triples(self, document: Document):
        # TODO
        return []
