from typing import Dict, Type, List, Optional
from pathlib import Path

from core.document import Document
from core.uddm.model import UDDM
from modules.base import BaseModule, ModuleResult
from modules.converter.normalizers.base import BaseNormalizer
from modules.converter.internal.base import BaseInternalConverter
from modules.converter.internal.docx_converter import DocxConverter
from modules.converter.external.base import BaseExternalConverter
from modules.converter.reverse.to_txt import UDDMToText
from modules.converter.reverse.to_html import UDDMToHTML
from modules.converter.reverse.to_tree import UDDMToTree


class ConverterRegistry:
    """Реестр всех доступных преобразований."""

    normalizers: Dict[str, Type[BaseNormalizer]] = {}                 # Lossless конвертеры форматов
    internal_converters: Dict[str, Type[BaseInternalConverter]] = {}  # Внутренние конвертеры
    external_converters: Dict[str, Type[BaseExternalConverter]] = {}  # Внешние конвертеры

    # Инициализация реестра
    # normalizers["doc"] = DocToDocxNormalizer
    internal_converters["docx"] = DocxConverter
    # external_converters["pdf"] = PdfConverter

    @staticmethod
    def get_normalizer(format_name: str) -> Optional[Type[BaseNormalizer]]:
        return ConverterRegistry.normalizers.get(format_name)

    @staticmethod
    def get_internal(format_name: str) -> Optional[Type[BaseInternalConverter]]:
        return ConverterRegistry.internal_converters.get(format_name)

    @staticmethod
    def get_external(format_name: str) -> Optional[Type[BaseExternalConverter]]:
        return ConverterRegistry.external_converters.get(format_name)

    @staticmethod
    def get_supported_formats() -> List[str]:
        return list(set(ConverterRegistry.normalizers.keys()) |
                    set(ConverterRegistry.internal_converters.keys()) |
                    set(ConverterRegistry.external_converters.keys()))

    @staticmethod
    def is_format_supported(format_name: str) -> bool:
        return format_name in ConverterRegistry.get_supported_formats()


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
