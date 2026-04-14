from pathlib import Path

from core.document import Document
from core.uddm.model import UDDM
from modules.base import BaseModule, ModuleResult
from modules.converter.registry import ConverterRegistry
from modules.converter.reverse.to_txt import UDDMToText
from modules.converter.reverse.to_html import UDDMToHTML
from modules.converter.reverse.to_tree import UDDMToTree


class Converter(BaseModule):
    """Модуль конвертации для извлечения структурированных данных в формате UDDM из оригинала документа."""

    def __init__(self):
        super().__init__()

    def execute(self, document: Document) -> ModuleResult:
        try:
            document.uddm = self._convert(document.original_file_path())
            document.uddm.save(document.uddm_file_path())

            # Различные визуальные представления UDDM
            UDDMToText().save(document.uddm, document.directory / "plain_text.txt")
            UDDMToHTML().save(document.uddm, document.directory / "uddm_html_view.html")
            UDDMToTree().save(document.uddm, document.directory / "uddm_tree_view.txt")

            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _convert(self, file_path: Path) -> UDDM:
        # Нормализация (преобразование без потерь)
        normalized_file = self._normalize(file_path)
        format_name = self._detect_format(normalized_file)

        # Внутренний конвертер
        internal_converter_cls = ConverterRegistry.get_internal(format_name)
        if internal_converter_cls:
            converter = internal_converter_cls()
            uddm = converter.convert(normalized_file)
            return uddm

        # Внешний конвертер
        external_converter_cls = ConverterRegistry.get_external(format_name)
        if external_converter_cls:
            converter = external_converter_cls()
            structured_data = converter.convert(normalized_file)
            uddm = converter.adapt_to_uddm(structured_data)
            return uddm

        raise RuntimeError(f"Нет подходящего конвертера для формата: {format_name}")

    def _normalize(self, file_path: Path) -> Path:
        """Рекуррентная нормализация."""
        format_name = self._detect_format(file_path)

        normalizer_cls = ConverterRegistry.get_normalizer(format_name)
        if not normalizer_cls:
            return file_path

        normalizer = normalizer_cls()
        normalized = normalizer.normalize(file_path)

        new_format = self._detect_format(normalized)
        if new_format == format_name:
            return normalized

        return self._normalize(normalized)

    @staticmethod
    def _detect_format(path: Path) -> str:
        return path.suffix.lower().replace(".", "")
