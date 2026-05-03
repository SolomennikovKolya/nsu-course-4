from modules.base import BaseModule, ModuleResult
from models.document import Document, DocumentContext


class Connector(BaseModule):
    """Добавление триплетов в онтологическую модель."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        try:
            raise NotImplementedError("Модуль не реализован")

        except Exception as ex:
            self.log_exception()
            return ModuleResult.failed(message=str(ex))
