from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from core.template.base import BaseTemplateCode
from core.template.field import Field


@dataclass
class Template:
    """Представляет информацию о шаблоне обработки документов."""

    name: str        # Название шаблона / класс документа. Пример: "Заявление на практику бакалавриат КНиС 7 семестр"
    directory: Path  # Директория, где хранятся данные шаблона

    description: Optional[str] = None  # Опциональный комментарий

    # Код шаблона. Загружается динамически из code.py при загрузке шаблона. Не сохраняется в meta.json
    code: Optional[BaseTemplateCode] = field(default=None, repr=False, metadata={'skip_dict': True})

    # Поля шаблона. Загружаются динамически методом code.fields()
    fields: Optional[List[Field]] = field(default=None, repr=False, metadata={'skip_dict': True})

    def code_file_path(self):
        return self.directory / "code.py"
