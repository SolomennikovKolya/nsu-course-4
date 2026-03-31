from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from enum import StrEnum, auto

from core.template.template import Template


@dataclass
class Document:
    """Модель документа в системе."""

    class Status(StrEnum):
        """Статусы обработки документа по ходу прохождения пайплайна."""

        UPLOADED = auto()          # Документ загружен в систему
        UDDM_EXTRACTED = auto()    # Построен UDDM
        CLASS_DETERMINED = auto()  # Определен класс документа
        TERMS_EXTRACTED = auto()   # Извлечены RDF-термы (индивидуумы + литералы)
        TERMS_VALIDATED = auto()   # Термы провалидированы
        TRIPLES_BUILT = auto()     # Построены RDF-триплеты
        ADDED_TO_MODEL = auto()    # Добавлены в онтологию

        def __int__(self):
            stages = {
                Document.Status.UPLOADED: 0,
                Document.Status.UDDM_EXTRACTED: 1,
                Document.Status.CLASS_DETERMINED: 2,
                Document.Status.TERMS_EXTRACTED: 3,
                Document.Status.TERMS_VALIDATED: 4,
                Document.Status.TRIPLES_BUILT: 5,
                Document.Status.ADDED_TO_MODEL: 6,
            }
            return stages[self]

    name: str            # Название документа (имя файла)
    directory: Path      # Директория с документом и его данными. Название директории соответствует имени документа

    status: Status = Status.UPLOADED     # Статус обработки документа
    doc_class: Optional[str] = None      # Класс документа (соответствует шаблону извлечения)
    # Шаблон обработки документа. Загружается динамически при определении класса документа
    template: Optional[Template] = field(default=None, repr=False, metadata={'skip_dict': True})

    def original_file_path(self):
        return self.directory / self.name

    def uddm_file_path(self):
        return self.directory / "uddm.xml"

    def rdf_file_path(self):
        return self.directory / "rdf.xml"
