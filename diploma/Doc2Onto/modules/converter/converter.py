from modules.base_module import BaseModule
from modules.converter.docx_to_ldml import DocxToLdmlConverter

from lxml import etree  # type: ignore
from pathlib import Path


class Converter(BaseModule):
    """
    Общий конвертер документов.

    Назначение:
    - Преобразует входной документ в единый внутренний формат LDML

    Реализация:
    - Определяет формат входного файла (DOC, DOCX, PDF и др.)
    - Делегирует обработку соответствующему специализированному конвертеру
    """

    def __init__(self):
        self.docx_to_ldml = DocxToLdmlConverter()

    def process(self, input_path: str | Path) -> etree._ElementTree:
        input_path = Path(input_path)
        suffix = input_path.suffix.lower()

        if suffix == ".docx":
            return self.docx_to_ldml.convert(input_path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")
