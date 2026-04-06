from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, TypeVar, Generic
import json
import hashlib
from typing import Iterator

from app.utils import smart_asdict


T = TypeVar("T")  # Объект, которым управляет менеджер
A = TypeVar("A")  # Аргумент для создания объекта
META_FILENAME = "meta.json"


class BaseManager(ABC, Generic[T, A]):
    """Абстрактный базовый класс для менеджеров хранилища."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def get(self, name: str) -> Optional[T]:
        pass

    @abstractmethod
    def add(self, arg: A) -> T:
        pass

    @abstractmethod
    def delete(self, obj: T):
        pass

    def iterate(self) -> Iterator[T]:
        """Итератор по всем объектам."""
        if not self.base_dir.exists():
            return

        for directory in self.base_dir.iterdir():
            obj = self.get(directory.name)
            if obj:
                yield obj

    def list(self) -> List[T]:
        """Возвращает список всех существующих объектов."""
        return list(self.iterate())

    def save_metadata(self, obj: T):
        """Сохраняет метаданные объекта."""
        data = smart_asdict(obj)  # type: ignore[arg-type]
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        directory = self._get_directory(obj)
        self._save_meta(directory, data)

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

    @abstractmethod
    def _get_directory(self, obj: T) -> Path:
        """Возвращает директорию, где хранится объект."""
        pass

    def _meta_path(self, directory: Path) -> Path:
        """Возвращает путь к файлу метаданных в директории."""
        return directory / META_FILENAME

    def _load_meta(self, directory: Path) -> Optional[dict]:
        """Загружает метаданные из мета-файла в заданной директории."""
        if not directory.exists() or not directory.is_dir():
            return None

        meta_file = self._meta_path(directory)
        if not meta_file.exists():
            return None

        with meta_file.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return None

    def _save_meta(self, directory: Path, data: dict):
        """Сохраняет метаданные."""
        meta_file = self._meta_path(directory)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _compute_hash(self, path: Path) -> str:
        """Вычисляет хеш файла."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
