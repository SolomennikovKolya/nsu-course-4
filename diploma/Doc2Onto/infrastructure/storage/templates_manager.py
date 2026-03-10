from pathlib import Path
from typing import Optional, List

from core.template.template import Template
from infrastructure.storage.base_manager import BaseManager

BASE_DIR = Path("data/templates")


class TemplatesManager(BaseManager[Template, str]):
    """
    Менеджер для управления шаблонами документов.

    Предполагается, что каждый шаблон хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени шаблона (то есть классу документа). 
    Внутри директории шаблона должен быть файл meta.json с метаданными шаблона, а также файлы, 
    описывающие шаблон (например, uddm_schema.xml, extraction_rules.py и т.д.).

    BASE_DIR
    └── template_i/
        ├── meta.json
        ├── uddm_schema.xml
        ├── extraction_rules.py
        ├── validation_rules.py
        └── classification_rules.py
    """

    def __init__(self, base_dir: Path = BASE_DIR):
        super().__init__(base_dir)

    def _get_directory(self, obj: Template) -> Path:
        return obj.directory

    def _object_from_meta(self, directory: Path) -> Optional[Template]:
        meta = self._load_meta(directory)

        # Чтобы считалось, что шаблон существует, достаточно наличия meta.json с полем name
        if not meta.get("name"):
            return None

        # Исправляем неконсистентность, если директория в мета не совпадает с реальной
        if not meta.get("directory") or Path(meta["directory"]) != directory:
            meta["directory"] = str(directory)

        return Template(
            name=str(meta.get("name")),
            directory=Path(meta["directory"]),
            description=str(meta["description"]) if meta.get("description") else None,
            uddm_schema=Path(meta["uddm_schema"]) if meta.get("uddm_schema") else None,
            extraction_rules=Path(meta["extraction_rules"]) if meta.get("extraction_rules") else None,
            validation_rules=Path(meta["validation_rules"]) if meta.get("validation_rules") else None,
            classification_rules=Path(meta["classification_rules"]) if meta.get("classification_rules") else None,
        )

    def _doc_class_from_meta(self, directory: Path) -> Optional[str]:
        meta = self._load_meta(directory)
        return meta.get("name")

    def add(self, name: str) -> Template:
        directory = self.base_dir / name

        if directory.exists():
            temp = self.get(name)
            if temp:
                return temp
        directory.mkdir(parents=True, exist_ok=True)

        template = Template(name=name, directory=directory)
        self.save_metadata(template)
        return template

    def doc_classes_list(self) -> List[str]:
        """Возвращает список всех существующих классов документов."""
        classes = []
        if not self.base_dir.exists():
            return classes

        for directory in self.base_dir.iterdir():
            if not directory.is_dir():
                continue

            doc_class = self._doc_class_from_meta(directory)
            if doc_class:
                classes.append(doc_class)

        return classes
