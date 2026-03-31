from pathlib import Path
from typing import Optional, List
import shutil

from core.template.template import Template
from infrastructure.storage.base_manager import BaseManager
from infrastructure.storage.template_loader import TemplateLoader

BASE_DIR = Path("data/templates")
EXAMPLE_TEMPLATE_PATH = Path("core/template/example.py")


class TemplateManager(BaseManager[Template, str]):
    """
    Менеджер для управления шаблонами документов.

    Предполагается, что каждый шаблон хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени шаблона (то есть классу документа). 
    Внутри директории шаблона должен быть файл meta.json и code.py (код шаблона).

    Минимальная структура:
    ```
    BASE_DIR
    └── template_i/
        ├── meta.json
        └── code.py
    ```
    """

    def __init__(self, base_dir: Path = BASE_DIR):
        super().__init__(base_dir)

        # Кэш для списка классов документов
        self.doc_classes: List[str] = []
        self._load_doc_classes()

    def get(self, name: str) -> Optional[Template]:
        """Возвращает шаблон по имени (классу документа). Автоматически загружает код шаблона."""
        template = super().get(name)
        if not template:
            return None

        template.code = TemplateLoader.load(template)
        return template

    def add(self, name: str) -> Template:
        """Создаёт новый шаблон с заданным именем (классом документа). Возвращает созданный шаблон."""
        directory = self.base_dir / name

        if directory.exists():
            temp = self.get(name)
            if temp:
                return temp
        directory.mkdir(parents=True, exist_ok=True)

        target_code = directory / "code.py"
        if not target_code.exists():
            shutil.copy(EXAMPLE_TEMPLATE_PATH, target_code)

        template = Template(name, directory)
        self.save_metadata(template)
        self.doc_classes.append(name)

        return template

    def doc_classes_list(self) -> List[str]:
        """Возвращает список всех существующих классов документов."""
        return self.doc_classes

    def _load_doc_classes(self):
        self.doc_classes.clear()
        if not self.base_dir.exists():
            return

        for directory in self.base_dir.iterdir():
            if not directory.is_dir():
                continue

            doc_class = self._doc_class_from_meta(directory)
            if doc_class:
                self.doc_classes.append(doc_class)

    def _doc_class_from_meta(self, directory: Path) -> Optional[str]:
        meta = self._load_meta(directory)
        return meta.get("name")

    def _get_directory(self, obj: Template) -> Path:
        return obj.directory

    def _is_directory_valid(self, directory: Path) -> bool:
        meta = self._load_meta(directory)
        return bool(meta) \
            and meta.get("name") == directory.name \
            and (directory / "code.py").exists()

    def _object_from_meta(self, directory: Path) -> Optional[Template]:
        if not self._is_directory_valid(directory):
            return None

        meta = self._load_meta(directory)
        return Template(
            name=str(meta.get("name")),
            directory=Path(meta["directory"]),
            description=str(meta["description"]) if meta.get("description") else None
        )
