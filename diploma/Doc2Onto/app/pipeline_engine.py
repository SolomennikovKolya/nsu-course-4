from app.modules import DummyProcessingModule
from core.document.document import Document


class PipelineEngine:

    def __init__(self):
        self.modules = [DummyProcessingModule()]

    def run(self, document: Document):
        for module in self.modules:
            document = module.execute(document)
        return document
