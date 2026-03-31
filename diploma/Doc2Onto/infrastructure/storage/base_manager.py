from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, TypeVar, Generic
import json
import hashlib

from app.utils import smart_asdict


T = TypeVar("T")  # Объект, которым управляет менеджер
A = TypeVar("A")  # Аргумент для создания объекта
META_FILENAME = "meta.json"


class BaseManager(ABC, Generic[T, A]):
    """Абстрактный базовый класс для менеджеров хранилища."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get(self, name: str) -> Optional[T]:
        """Возвращает один объект по имени."""
        directory = self.base_dir / name
        return self._object_from_meta(directory)

    @abstractmethod
    def add(self, arg: A) -> T:
        """Сохраняет новый объект."""
        pass

    def list(self) -> List[T]:
        """Возвращает список всех существующих объектов."""
        items = []
        if not self.base_dir.exists():
            return items

        for directory in self.base_dir.iterdir():
            obj = self._object_from_meta(directory)
            if obj:
                items.append(obj)

        return items

    def save_metadata(self, obj: T):
        """Сохраняет метаданные объекта."""
        data = smart_asdict(obj)  # type: ignore[arg-type]
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        directory = self._get_directory(obj)
        self._save_meta(directory, data)

    @abstractmethod
    def _get_directory(self, obj: T) -> Path:
        """Возвращает директорию, где хранится объект."""
        pass

    @abstractmethod
    def _is_directory_valid(self, directory: Path) -> bool:
        """Проверяет структуру директории на соответствие внутренним стандартам хранения."""
        pass

    @abstractmethod
    def _object_from_meta(self, directory: Path) -> Optional[T]:
        """Десериализует объект из метаданных."""
        pass

    def _compute_hash(self, path: Path) -> str:
        """Вычисляет хеш файла."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _meta_path(self, directory: Path) -> Path:
        """Возвращает путь к файлу метаданных в директории."""
        return directory / META_FILENAME

    def _load_meta(self, directory: Path) -> dict:
        """Загружает метаданные из мета-файла в заданной директории."""
        if not directory.exists() or not directory.is_dir():
            return {}

        meta_file = self._meta_path(directory)
        if not meta_file.exists():
            return {}

        with meta_file.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_meta(self, directory: Path, data: dict):
        """Сохраняет метаданные."""
        meta_file = self._meta_path(directory)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
