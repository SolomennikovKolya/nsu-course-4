from abc import ABC, abstractmethod
from pathlib import Path


class BaseExternalConverter(ABC):

    @abstractmethod
    def convert(self, file_path: Path):
        """Запускает внешний конвертер. Возвращает структурированные данные."""
        pass

    @abstractmethod
    def adapt_to_uddm(self, structured_data) -> Path:
        """Преобразует результат внешнего инструмента в UDDM."""
        pass
