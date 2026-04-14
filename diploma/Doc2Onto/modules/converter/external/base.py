from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.uddm.model import UDDM


class BaseExternalConverter(ABC):

    @abstractmethod
    def convert(self, file_path: Path) -> Any:
        """Запускает внешний конвертер. Возвращает структурированные данные."""
        pass

    @abstractmethod
    def adapt_to_uddm(self, structured_data: Any) -> UDDM:
        """Преобразует результат внешнего инструмента в UDDM."""
        pass
