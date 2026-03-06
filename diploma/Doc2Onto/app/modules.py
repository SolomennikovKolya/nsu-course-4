from core.status import DocumentStatus
from app.base_module import BaseModule


class DummyProcessingModule(BaseModule):

    def execute(self, document):
        document.status = DocumentStatus.PROCESSED
        return document
