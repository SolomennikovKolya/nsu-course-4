from abc import ABC, abstractmethod
from pathlib import Path


class BaseNormalizer(ABC):

    target_format: str

    @abstractmethod
    def normalize(self, file_path: Path) -> Path:
        """
        Выполняет lossless преобразование файла.
        Возвращает путь к нормализованному файлу.
        """
        pass
