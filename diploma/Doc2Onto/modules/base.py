from abc import ABC, abstractmethod
from enum import Enum
from logging import ERROR

from app.context import get_logger
from core.document import Document


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

    def __init__(self) -> None:
        super().__init__()

        self._logger = get_logger()

    @abstractmethod
    def execute(self, document: Document) -> ModuleResult:
        pass

    def log(self, level: int, message: str, exc_info: bool = False):
        self._logger.log(level, f"    [{self.__class__.__name__}] " + message, exc_info=exc_info)

    def log_exception(self):
        self._logger.log(ERROR, f"    [{self.__class__.__name__}] Exception occurred", exc_info=True)
