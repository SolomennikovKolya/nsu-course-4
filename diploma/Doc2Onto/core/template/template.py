from dataclasses import dataclass
from pathlib import Path


@dataclass
class Template:
    """
    Шаблон обработки документов.
    Соответствует классу документов в системе.
    """

    name: str        # Название шаблона (класс документа)
    directory: Path  # Директория шаблона

    description: str | None = None
