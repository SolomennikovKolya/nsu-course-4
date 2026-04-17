from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from enum import StrEnum, auto

from core.template.template import Template


@dataclass
class Document:
    """
    Легковесная модель документа в системе. Предоставляет всю необходимую информацию для работы с документом.
    Не хранит в себе промежуточных данных обработки (UDDM, полный текст, триплеты и т.д.), а только ссылки на них.
    """

    class Status(StrEnum):
        """Статусы обработки документа по ходу прохождения пайплайна."""

        UPLOADED = auto()          # Документ загружен в систему
        UDDM_EXTRACTED = auto()    # Построен UDDM
        CLASS_DETERMINED = auto()  # Определен класс документа
        FIELDS_EXTRACTED = auto()  # Извлечены поля (индивидуумы + литералы)
        FIELDS_VALIDATED = auto()  # Поля провалидированы
        TRIPLES_BUILT = auto()     # Построены триплеты
        ADDED_TO_MODEL = auto()    # Знания добавлены в онтологию

        def __int__(self):
            stages = {
                Document.Status.UPLOADED: 0,
                Document.Status.UDDM_EXTRACTED: 1,
                Document.Status.CLASS_DETERMINED: 2,
                Document.Status.FIELDS_EXTRACTED: 3,
                Document.Status.FIELDS_VALIDATED: 4,
                Document.Status.TRIPLES_BUILT: 5,
                Document.Status.ADDED_TO_MODEL: 6,
            }
            return stages[self]

    name: str                         # Название документа (имя оригинального файла)
    directory: Path                   # Директория с документом и его данными
    status: Status = Status.UPLOADED  # Статус обработки документа
    doc_class: Optional[str] = None   # Класс документа (название шаблона)
    template: Optional[Template] = field(default=None, repr=False, metadata={'skip_dict': True})  # Ссылка на шаблон извлечения

    # ----- пути к файлам -----

    def original_file_path(self):
        return self.directory / self.name

    def uddm_file_path(self):
        return self.directory / "uddm.xml"

    def plain_text_file_path(self):
        return self.directory / "plain_text.txt"

    def uddm_html_view_file_path(self):
        return self.directory / "uddm_html_view.html"

    def uddm_tree_view_file_path(self):
        return self.directory / "uddm_tree_view.txt"

    def extraction_result_file_path(self):
        return self.directory / "extraction_result.json"

    def validation_result_file_path(self):
        return self.directory / "validation_result.json"

    def rdf_file_path(self):
        return self.directory / "rdf.xml"
