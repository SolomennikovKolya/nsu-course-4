from typing import Dict, Type, List, Optional

from modules.converter.normalizers.base import BaseNormalizer
from modules.converter.internal.base import BaseInternalConverter
from modules.converter.internal.docx_converter import DocxConverter
from modules.converter.external.base import BaseExternalConverter


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
