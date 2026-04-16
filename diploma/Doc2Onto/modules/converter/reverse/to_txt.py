from typing import List

from core.uddm.model import UDDM
from modules.converter.reverse.base import BaseReverseConverter


class UDDMToText(BaseReverseConverter):

    def convert(self, uddm: UDDM) -> str:
        """Преобразует UDDM в простой текст без структуры."""
        return str(uddm.root)
