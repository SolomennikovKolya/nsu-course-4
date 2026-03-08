from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Template:
    """Шаблон обработки документов."""

    name: str        # Название шаблона / класс документа. Пример: "Заявление на практику бакалавриат КНиС 7 семестр"
    directory: Path  # Директория шаблона

    description: Optional[str] = None

    # Путь к файлу с типичной UDDM схеомой документа данного класса.
    # Схема не обязательно должна совпадать для всех документов класса,
    # но правила извлечения и классификации могут опираться на неё
    uddm_schema: Optional[Path] = None

    extraction_rules: Optional[Path] = None      # Путь к файлу с извлеченными знаниями в формате RDF
    validation_rules: Optional[Path] = None      # Путь к файлу с провалидированными знаниями
    classification_rules: Optional[Path] = None  # Путь к файлу с провалидированными знаниями
