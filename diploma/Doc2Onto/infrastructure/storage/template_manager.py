import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.settings import TEMPLATES_DIR, TEMPLATE_CODE_EXAMPLE_PATH
from app.context import get_logger
from models.template import Template
from infrastructure.storage.base_manager import BaseManager


class TemplateManager(BaseManager[Template, str]):
    """
    Менеджер для управления шаблонами документов.

    Каждый шаблон хранится в каталоге ``<uuid>/`` с meta.json и code.py.
    Отображаемое имя и описание — только в meta.json.

    Минимальная структура:
    ```
    BASE_DIR
    └── <uuid>/
        ├── meta.json
        └── code.py
    ```
    """

    def __init__(self, base_dir: Path = TEMPLATES_DIR):
        super().__init__(base_dir)
        self.logger = get_logger()

    def get(self, template_id: str) -> Optional[Template]:
        """Возвращает шаблон по ID."""
        directory = self.base_dir / template_id
        if not directory.is_dir():
            return None

        meta = self._load_meta(directory)
        if not meta:
            return None

        directory, meta = self._maybe_migrate_legacy(directory, meta)
        if not self._is_directory_valid(directory, meta):
            return None

        return self._template_from_meta(directory, meta)

    def add(self, name: str) -> Template:
        """Создаёт новый шаблон с заданным отображаемым именем."""
        name = name.strip()
        if not name:
            raise ValueError("Имя шаблона не может быть пустым")

        existing = next((t for t in self.list() if t.name == name), None)
        if existing:
            return existing

        tid = str(uuid.uuid4())
        directory = self.base_dir / tid
        directory.mkdir(parents=True, exist_ok=True)

        target_code = directory / "code.py"
        if not target_code.exists():
            shutil.copy(TEMPLATE_CODE_EXAMPLE_PATH, target_code)

        template = Template(id=tid, name=name, directory=directory)
        self.save_metadata(template)
        return template

    def delete(self, temp: Template):
        """Удаляет шаблон из системы."""
        directory = self._get_directory(temp)
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)

    def rename(self, temp: Template, new_name: str):
        """Меняет только отображаемое имя в meta.json (каталог не переименовывается)."""
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Имя шаблона не может быть пустым")

        if new_name == temp.name:
            return

        for other in self.list():
            if other.id != temp.id and other.name == new_name:
                raise FileExistsError(f'Шаблон с названием "{new_name}" уже существует')

        temp.name = new_name
        self.save_metadata(temp)

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

    def _get_directory(self, obj: Template) -> Path:
        return obj.directory

    def _template_from_meta(self, directory: Path, meta: dict) -> Template:
        return Template(
            id=meta["id"],
            name=str(meta.get("name") or ""),
            directory=directory,
            description=str(meta["description"]) if meta.get("description") else None,
        )

    def _maybe_migrate_legacy(self, directory: Path, meta: dict) -> Tuple[Path, dict]:
        """
        Старый формат: каталог назывался по имени шаблона.
        Переносим в каталог UUID, в meta добавляем id.
        """
        if meta.get("id") == directory.name and (directory / "code.py").is_file():
            return directory, meta

        folder = directory.name
        if meta.get("name") != folder:
            return directory, meta
        if not (directory / "code.py").is_file():
            return directory, meta

        new_id = str(uuid.uuid4())
        new_dir = self.base_dir / new_id
        directory.rename(new_dir)
        meta = dict(meta)
        meta["id"] = new_id
        meta["directory"] = str(new_dir)
        self._save_meta(new_dir, meta)
        return new_dir, meta

    def _is_directory_valid(self, directory: Path, meta: dict) -> bool:
        if not meta.get("id") or meta["id"] != directory.name:
            return False
        if not meta.get("name"):
            return False
        if not (directory / "code.py").is_file():
            return False
        if meta.get("directory") != str(directory):
            meta["directory"] = str(directory)
        return True
