import shutil
from pathlib import Path
from typing import Optional, Tuple

from app.settings import DOCUMENTS_BASE_DIR
from core.document import Document
from infrastructure.storage.base_manager import BaseManager


class DocumentManager(BaseManager[Document, Path]):
    """
    Менеджер для управления документами в файловой системе.

    Предполагается, что каждый документ хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени документа. Внутри директории документа должен быть 
    оригинальный файл (имя которого совпадает с названием директории) и файл meta.json с метаданными документа.
    Также в этой директории могут храняться промежуточные файлы обработки документа.

    Минимальная структура:
    ```
    BASE_DIR
    └── document_i.docx/
        ├── meta.json
        └── document_i.docx
    ```
    """

    def __init__(self, base_dir: Path = DOCUMENTS_BASE_DIR):
        super().__init__(base_dir)

    def get(self, name: str) -> Optional[Document]:
        """Возвращает документ по имени."""
        directory = self.base_dir / name

        valid, meta = self._is_directory_valid(directory)
        if not valid or not meta:
            return None

        doc = Document(
            name=directory.name,
            directory=directory,
            status=Document.Status(meta.get("status", Document.Status.UPLOADED)),
            doc_class=meta.get("doc_class"),
            pipeline_failed_target=Document.Status(
                meta.get("pipeline_failed_target")) if meta.get("pipeline_failed_target") else None,
            pipeline_error_message=meta.get("pipeline_error_message"),
        )
        return doc

    def add(self, file_path: Path) -> Document:
        """Добавляет новый документ в систему."""
        name = file_path.name
        directory = self.base_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        target_file = directory / name

        # Если файл уже есть в системе и совпадает - возвращаем существующий документ
        if target_file.exists():
            if self._compute_hash(target_file) == self._compute_hash(file_path):
                doc = self.get(name)
                if doc:
                    return doc

        shutil.copy(file_path, target_file)

        doc = Document(name, directory)
        self.save_metadata(doc)
        return doc

    def delete(self, doc: Document):
        """Удаляет документ из системы."""
        if doc.directory.exists() and doc.directory.is_dir():
            shutil.rmtree(doc.directory)

    def rename(self, doc: Document, new_name: str):
        """Переименовывает документ (директорию и оригинальный файл), обновляет meta.json."""
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("Имя документа не может быть пустым")

        if new_name == doc.name:
            return

        old_name = doc.name
        old_dir = self.base_dir / old_name
        old_file = old_dir / old_name
        if not old_dir.exists():
            raise FileNotFoundError(f'Документ "{old_name}" не найден в хранилище.')
        if not old_file.exists():
            raise FileNotFoundError(f'Оригинальный файл "{old_name}" не найден.')

        new_dir = self.base_dir / new_name
        if new_dir.exists():
            raise FileExistsError(f'Документ с названием "{new_name}" уже существует.')

        try:
            old_dir.rename(new_dir)
        except OSError as exc:
            raise OSError(str(exc))

        # После переименования директории надо переименовать оригинальный файл.
        new_file = new_dir / new_name
        old_file_in_new_dir = new_dir / old_name
        try:
            if old_file_in_new_dir.exists() and not new_file.exists():
                old_file_in_new_dir.rename(new_file)
        except OSError as exc:
            # Пытаемся откатить директорию обратно, чтобы не оставить систему в полусостоянии.
            try:
                new_dir.rename(old_dir)
            except OSError:
                pass
            raise OSError(str(exc))

        doc.name = new_name
        doc.directory = new_dir
        self.save_metadata(doc)

    def is_file_exists(self, file_path: Path) -> bool:
        """Проверяет, существует ли файл в системе."""
        name = file_path.name
        file_dir = self.base_dir / name
        if not file_dir.exists() or not file_dir.is_dir():
            return False

        target_file = file_dir / name
        return target_file.exists() and self._compute_hash(target_file) == self._compute_hash(file_path)

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

    def _get_directory(self, obj: Document) -> Path:
        return obj.directory

    def _is_directory_valid(self, directory: Path) -> Tuple[bool, Optional[dict]]:
        """
        Проверяет, что директория соответствует структуре хранения документа и содержит необходимые файлы.
        Возвращает кортеж (is_valid, meta), где is_valid - булево значение, указывающее на валидность директории,
        а meta - словарь с метаданными документа (или None, если мета не подгрузилась).
        """
        meta = self._load_meta(directory)
        valid = bool(meta) \
            and meta.get("name") == directory.name \
            and meta.get("directory") == str(directory) \
            and (directory / directory.name).exists()

        return valid, meta
