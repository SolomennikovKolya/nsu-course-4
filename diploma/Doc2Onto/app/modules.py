from core.document.status import DocumentStatus
from app.base_module import BaseModule


class DummyProcessingModule(BaseModule):

    def execute(self, document):
        document.status = DocumentStatus.ADDED_TO_MODEL
        return document
