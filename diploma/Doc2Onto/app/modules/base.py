from abc import ABC, abstractmethod
from enum import Enum

from core.document.document import Document


class ModuleResult(Enum):
    """Результат выполнения модуля."""

    OK = "ok"
    FAILED = "failed"

    def __str__(self):
        return self.value

    def __int__(self):
        return int(self.value == ModuleResult.OK)


class BaseModule(ABC):
    """
    Абстрактный класс для всех модулей обработки документов. 
    Каждый модуль должен реализовывать метод execute.
    """

    @abstractmethod
    def execute(self, document: Document) -> ModuleResult:
        pass
