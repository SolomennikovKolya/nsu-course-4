import json
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict

from core.template.template import Template

BASE_DIR = Path("data/templates")
META_FILENAME = "meta.json"


class TemplatesManager:
    """
    Менеджер для управления шаблонами документов.

    Предполагается, что каждый шаблон хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени шаблона (то есть классу документа). 
    Внутри директории шаблона должен быть файл meta.json с метаданными шаблона, а также файлы, 
    описывающие шаблон (например, uddm_schema.xml, extraction_rules.py и т.д.).

    Пример структуры:
    BASE_DIR
    └── template_i/
        ├── meta.json
        ├── uddm_schema.xml
        ├── extraction_rules.py
        ├── validation_rules.py
        └── classification_rules.py
    """

    def __init__(self, base_dir: Path = BASE_DIR):
        self.base_dir: Path = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, directory: Path) -> Path:
        return directory / META_FILENAME

    def _load_meta(self, directory: Path) -> dict:
        if not directory.exists() or not directory.is_dir():
            return {}

        meta_file = self._meta_path(directory)
        if not meta_file.exists():
            return {}

        with meta_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_meta(self, directory: Path, data: dict):
        meta_file = self._meta_path(directory)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _template_from_meta(self, directory: Path) -> Optional[Template]:
        """Десериализует объект Template из метаданных в директории."""
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

    def list_templates(self) -> List[Template]:
        """Возвращает список всех шаблонов."""
        templates = []
        if not self.base_dir.exists():
            return templates

        for directory in self.base_dir.iterdir():
            if not directory.is_dir():
                continue

            temp = self._template_from_meta(directory)
            if temp:
                templates.append(temp)

        return templates

    def get(self, name: str) -> Optional[Template]:
        """Возвращает шаблон по имени."""
        directory = self.base_dir / name
        return self._template_from_meta(directory) if directory.exists() else None

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

    def save_metadata(self, template: Template):
        """Сохраняет метаданные шаблона."""
        data = asdict(template)

        # Path -> str
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        self._save_meta(template.directory, data)
