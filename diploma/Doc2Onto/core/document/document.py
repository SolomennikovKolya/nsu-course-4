from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from core.document.status import DocumentStatus


@dataclass
class Document:
    """Класс, представляющий документ в системе, с его метаданными и статусом обработки."""

    name: str                        # Название документа (имя файла)
    directory: Path                  # Директория с документом и его данными. Название директории соответствует имени документа
    filepath: Optional[Path] = None  # Путь к оригинальному файлу (автоматически заполняется как directory / name)

    status: DocumentStatus = DocumentStatus.UPLOADED  # Статус обработки документа
    doc_type: Optional[str] = None                    # Тип документа (соответствует шаблону обработки)

    uddm_file: Optional[Path] = None           # Путь к файлу с извлеченными данными в формате UDDM
    rdf_file: Optional[Path] = None            # Путь к файлу с извлеченными знаниями в формате RDF
    validated_rdf_file: Optional[Path] = None  # Путь к файлу с провалидированными знаниями

    def __post_init__(self):
        """Автоматически заполняет filepath как directory / name если не задан."""
        if self.filepath is None:
            self.filepath = self.directory / self.name
