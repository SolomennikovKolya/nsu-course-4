from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, TypeVar, Generic
from dataclasses import asdict
import json
import hashlib


T = TypeVar("T")  # Объект, которым управляет менеджер
A = TypeVar("A")  # Аргумент для создания объекта
META_FILENAME = "meta.json"


class BaseManager(ABC, Generic[T, A]):
    """Абстрактный базовый класс для менеджеров хранилища, задающий публичный контракт и реализующий общие методы."""

    def __init__(self, base_dir: Path):
        """Инициализирует менеджер над базовой директорией для хранения объектов."""
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

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
            return json.load(f)

    def _save_meta(self, directory: Path, data: dict):
        """Сохраняет метаданные."""
        meta_file = self._meta_path(directory)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @abstractmethod
    def _object_from_meta(self, directory: Path) -> Optional[T]:
        """Десериализует объект из метаданных."""
        pass

    @abstractmethod
    def _get_directory(self, obj: T) -> Path:
        """Возвращает директорию, где хранится объект."""
        pass

    # ========== ПУБЛИЧНЫЙ КОНТРАКТ ==========

    def list(self) -> List[T]:
        """Возвращает список всех объектов."""
        items = []
        if not self.base_dir.exists():
            return items

        for directory in self.base_dir.iterdir():
            if not directory.is_dir():
                continue

            obj = self._object_from_meta(directory)
            if obj:
                items.append(obj)

        return items

    def get(self, name: str) -> Optional[T]:
        """Возвращает один объект по имени."""
        directory = self.base_dir / name
        return self._object_from_meta(directory) if directory.exists() else None

    @abstractmethod
    def add(self, arg: A) -> T:
        """Сохраняет новый объект."""
        pass

    def save_metadata(self, obj: T):
        """Сохраняет метаданные объекта."""
        data = asdict(obj)  # type: ignore[arg-type]

        # Path -> str
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        directory = self._get_directory(obj)
        self._save_meta(directory, data)
