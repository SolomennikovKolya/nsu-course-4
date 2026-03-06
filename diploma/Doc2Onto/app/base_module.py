from abc import ABC, abstractmethod
from core.document import Document


class BaseModule(ABC):

    @abstractmethod
    def execute(self, document: Document) -> Document:
        pass
