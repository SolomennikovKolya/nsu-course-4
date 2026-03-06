from app.modules import DummyProcessingModule


class PipelineEngine:

    def __init__(self):
        self.modules = [DummyProcessingModule()]

    def run(self, document):
        for module in self.modules:
            document = module.execute(document)
        return document
