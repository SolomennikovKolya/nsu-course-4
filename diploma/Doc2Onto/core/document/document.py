from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from core.document.status import DocumentStatus


@dataclass
class Document:
    """Модель документа в системе."""

    name: str            # Название документа (имя файла)
    directory: Path      # Директория с документом и его данными. Название директории соответствует имени документа
    original_file: Path  # Путь к оригиналу (обязан существовать, чтобы считалось, что документ есть в системе)

    status: DocumentStatus = DocumentStatus.UPLOADED  # Статус обработки документа
    doc_class: Optional[str] = None                   # Класс документа (соответствует шаблону извлечения)

    uddm_file: Optional[Path] = None           # Путь к файлу с извлеченными данными в формате UDDM
    rdf_file: Optional[Path] = None            # Путь к файлу с извлеченными знаниями в формате RDF
    validated_rdf_file: Optional[Path] = None  # Путь к файлу с провалидированными знаниями
