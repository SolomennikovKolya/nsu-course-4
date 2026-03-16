from pathlib import Path

from app.modules.base import BaseModule, ModuleResult
from app.modules.converter.registry import ConverterRegistry
from core.document.document import Document
from core.document.status import DocumentStatus


class Converter(BaseModule):
    """Модуль конвертации для извлечения структурированных данных в формате UDDM из оригинала документа."""

    def execute(self, document: Document) -> ModuleResult:
        try:
            path_to_save_uddm = document.directory / "uddm.xml"
            self._convert(document.original_file, path_to_save_uddm)

            document.uddm_file = path_to_save_uddm
            document.status = DocumentStatus.UDDM_EXTRACTED
            return ModuleResult.OK

        except Exception:
            return ModuleResult.FAILED

    def _convert(self, file_path: Path, path_to_save_uddm: Path):
        # Нормализация (преобразование без потерь)
        normalized_file = self._normalize(file_path)
        format_name = self._detect_format(normalized_file)

        # Внутренний конвертер
        internal_converter_cls = ConverterRegistry.get_internal(format_name)
        if internal_converter_cls:
            converter = internal_converter_cls()
            uddm = converter.convert(normalized_file)
            uddm.save(path_to_save_uddm)
            return

        # Внешний конвертер
        external_converter_cls = ConverterRegistry.get_external(format_name)
        if external_converter_cls:
            converter = external_converter_cls()
            structured_data = converter.convert(normalized_file)
            converter.adapt_to_uddm(structured_data)
            return

        raise RuntimeError(f"No converter found for format: {format_name}")

    @staticmethod
    def _detect_format(path: Path) -> str:
        return path.suffix.lower().replace(".", "")

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
