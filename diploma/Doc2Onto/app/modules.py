from core.document.status import DocumentStatus
from app.base_module import BaseModule
from core.document.document import Document


class DummyProcessingModule(BaseModule):

    def execute(self, document: Document) -> Document:
        document.status = DocumentStatus.ADDED_TO_MODEL
        return document
