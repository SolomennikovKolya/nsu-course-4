"""
Нормализация PDF → DOCX через облако `ConvertAPI <https://www.convertapi.com/>`_.

Ключ API: переменная окружения ``CONVERTAPI_SECRET``
Результат — один ``.docx`` рядом с исходным PDF (то же имя, расширение ``.docx``).
"""

from __future__ import annotations

import os
from pathlib import Path

import convertapi

from modules.converter.normalizers.base import BaseNormalizer


def _api_secret() -> str | None:
    return os.getenv("CONVERTAPI_SECRET")


class PdfToDocx(BaseNormalizer):
    """Нормализатор: PDF → DOCX для последующей обработки ``DocxToUDDM``."""

    target_format = "docx"

    def normalize(self, file_path: Path) -> Path:
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Ожидался файл .pdf, получено: {file_path}")

        secret = _api_secret()
        if not secret or not secret.strip():
            raise RuntimeError(
                "Для конвертации PDF задайте переменную окружения CONVERTAPI_SECRET "
                "(секретный ключ ConvertAPI)."
            )

        convertapi.api_credentials = secret.strip()

        dest = file_path.with_suffix(".docx")
        result = convertapi.convert(
            "docx",
            {"File": str(file_path.resolve())},
            from_format="pdf",
        )
        result.file.save(str(dest))
        if not dest.is_file():
            raise RuntimeError(f"ConvertAPI: не удалось сохранить файл: {dest}")
        return dest
