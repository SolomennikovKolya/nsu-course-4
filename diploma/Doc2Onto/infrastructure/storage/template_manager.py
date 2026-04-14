from pathlib import Path
from typing import Optional, List, Tuple
import shutil

from app.context import get_logger
from core.template.template import Template
from infrastructure.storage.base_manager import BaseManager
from infrastructure.storage.template_loader import TemplateLoader

BASE_DIR = Path("data/templates")
CODE_EXAMPLE_PATH = Path("core/template/code_example.py")


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

        self.logger = get_logger()
        self.doc_classes: List[str] = []  # Кэш для списка классов документов
        self._load_doc_classes()

    def get(self, name: str) -> Optional[Template]:
        """Возвращает шаблон по имени (классу документа)."""
        directory = self.base_dir / name

        valid, meta = self._is_directory_valid(directory)
        if not valid or not meta:
            return None

        temp = Template(
            name=str(meta.get("name")),
            directory=Path(meta["directory"]),
            description=str(meta["description"]) if meta.get("description") else None,
            fields=None
        )

        temp.code = TemplateLoader.load(temp)
        if temp.code is None:
            self.logger.error(f"[TemplateManager] Template {temp.name} does not have code.")
            return None

        return temp

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
            shutil.copy(CODE_EXAMPLE_PATH, target_code)

        template = Template(name, directory)
        self.save_metadata(template)
        self.doc_classes.append(name)

        return template

    def delete(self, temp: Template):
        """Удаляет шаблон из системы."""
        directory = self._get_directory(temp)
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)

        if temp.name in self.doc_classes:
            self.doc_classes.remove(temp.name)

    def rename(self, temp: Template, new_name: str):
        """
        Переименовывает шаблон. В случае ошибки выбрасывает исключение.
        Синхронизацию ``doc_class`` у документов нужно выполнять отдельно (см. ``DocumentManager``).
        """
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Имя шаблона не может быть пустым")

        if new_name == temp.name:
            return

        new_path = self.base_dir / new_name
        if new_path.exists():
            raise FileExistsError(f'Шаблон с именем "{new_name}" уже существует')

        old_name = temp.name
        old_path = self.base_dir / old_name

        try:
            old_path.rename(new_path)
        except OSError as exc:
            raise exc

        temp.name = new_name
        temp.directory = new_path
        self.save_metadata(temp)

        if old_name in self.doc_classes:
            self.doc_classes[self.doc_classes.index(old_name)] = new_name
        elif new_name not in self.doc_classes:
            self.doc_classes.append(new_name)

    def doc_classes_list(self) -> List[str]:
        """Возвращает список всех существующих классов документов."""
        return self.doc_classes

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

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
        if not meta:
            return None
        return meta.get("name")

    def _get_directory(self, obj: Template) -> Path:
        return obj.directory

    def _is_directory_valid(self, directory: Path) -> Tuple[bool, Optional[dict]]:
        """
        Проверяет, что директория соответствует структуре хранения шаблона и содержит необходимые файлы.
        Возвращает кортеж (is_valid, meta), где is_valid - булево значение, указывающее на валидность директории,
        а meta - словарь с метаданными шаблона (или None, если мета не подгрузилась).
        """
        meta = self._load_meta(directory)
        valid = bool(meta) \
            and meta.get("name") == directory.name \
            and (directory / "code.py").exists()

        return valid, meta
