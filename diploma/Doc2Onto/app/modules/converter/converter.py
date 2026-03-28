from pathlib import Path

from app.modules.base import BaseModule, ModuleResult
from app.modules.converter.registry import ConverterRegistry
from app.modules.converter.reverse.to_txt import UDDMToText
from app.modules.converter.reverse.to_html import UDDMToHTML
from app.modules.converter.reverse.to_tree import UDDMToTree
from core.document.document import Document
from core.document.status import DocumentStatus
from core.uddm.uddm import UDDM


class Converter(BaseModule):
    """Модуль конвертации для извлечения структурированных данных в формате UDDM из оригинала документа."""

    def execute(self, document: Document) -> ModuleResult:
        try:
            uddm = self._convert(document.original_file)
            path_to_save_uddm = document.directory / "uddm.xml"
            uddm.save(path_to_save_uddm)

            # Различные визуальные представления UDDM
            UDDMToText().save(uddm, document.directory / "plain_text.txt")
            UDDMToHTML().save(uddm, document.directory / "uddm_html_view.html")
            UDDMToTree().save(uddm, document.directory / "uddm_tree_view.txt")

            document.uddm_file = path_to_save_uddm
            document.status = DocumentStatus.UDDM_EXTRACTED
            return ModuleResult.OK

        except Exception:
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

        raise RuntimeError(f"No converter found for format: {format_name}")

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
