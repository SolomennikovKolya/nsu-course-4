from abc import ABC, abstractmethod
from pathlib import Path

from core.uddm.uddm import UDDM


class BaseInternalConverter(ABC):

    @abstractmethod
    def convert(self, file_path: Path) -> UDDM:
        """Конвертирует файл напрямую в UDDM."""
        pass
