from abc import ABC, abstractmethod
from pathlib import Path

from core.uddm.uddm import UDDM


class BaseReverseConverter(ABC):

    @abstractmethod
    def convert(self, uddm: UDDM) -> str:
        """Конвертирует UDDM в другой текстовый формат."""
        pass

    def save(self, uddm: UDDM, path: Path):
        """Сохраняет UDDM в виде другого текстового формата в файл."""
        text = self.convert(uddm)
        path.write_text(text, encoding="utf-8")
