from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional, Self
from logging import ERROR

from app.context import get_logger
from models.document import DocumentContext


@dataclass(frozen=True)
class ModuleResult:
    """Результат выполнения модуля."""

    OK = "OK"
    FAILED = "FAILED"

    success: bool
    message: Optional[str] = None

    @classmethod
    def ok(cls, *, message: Optional[str] = None) -> Self:
        return cls(success=True, message=message)

    @classmethod
    def failed(cls, *, message: Optional[str] = None) -> Self:
        return cls(success=False, message=message)

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        return self.OK if self.success else self.FAILED

    def __int__(self) -> int:
        return int(self.success)


class BaseModule(ABC):
    """
    Абстрактный класс для всех модулей обработки документов. 
    Каждый модуль должен реализовывать метод execute.
    """

    def __init__(self):
        super().__init__()

        self._logger = get_logger()

    @abstractmethod
    def execute(self, ctx: DocumentContext) -> ModuleResult:
        pass

    def log(self, level: int, message: str, exc_info: bool = False):
        self._logger.log(level, f"    [{self.__class__.__name__}] " + message, exc_info=exc_info)

    def log_exception(self):
        self._logger.log(ERROR, f"    [{self.__class__.__name__}] Exception occurred", exc_info=True)
