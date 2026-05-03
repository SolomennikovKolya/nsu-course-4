import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.settings import DOCUMENTS_DIR
from models.document import ORIGINAL_FILE_STEM, Document
from infrastructure.storage.base_manager import BaseManager


class DocumentManager(BaseManager[Document, Path]):
    """
    Менеджер для управления документами в файловой системе.

    Каждый документ хранится в отдельной директории внутри BASE_DIR, имя каталога — уникальный
    ID документа (UUID). Внутри: оригинальный файл ``original{расширение}`` (ID только в meta.json),
    meta.json и прочие артефакты.

    Минимальная структура:
    ```
    BASE_DIR
    └── <uuid>/
        ├── meta.json
        └── original.docx
    ```
    """

    def __init__(self, base_dir: Path = DOCUMENTS_DIR):
        super().__init__(base_dir)

    def get(self, doc_id: str) -> Optional[Document]:
        """Возвращает документ по ID (имя каталога)."""
        directory = self.base_dir / doc_id
        if not directory.is_dir():
            return None

        meta = self._load_meta(directory)
        if not meta:
            return None

        valid = self._is_directory_valid(directory, meta)
        if not valid:
            return None

        doc = Document(
            id=meta["id"],
            original_suffix=meta["original_suffix"],
            directory=directory,
            name=meta.get("name") or "",
        )
        self._apply_meta_to_document(doc, meta)
        self._resolve_doc_class_to_template_id(doc)
        return doc

    def add(self, file_path: Path) -> Document:
        """Добавляет новый документ в систему."""
        display_name = file_path.name
        suffix = file_path.suffix
        if not suffix:
            raise ValueError("У загружаемого файла должно быть расширение")

        for existing in self.list():
            existing_path = existing.original_file_path()
            if existing_path.is_file() and self._compute_hash(existing_path) == self._compute_hash(
                file_path
            ):
                return existing

        doc_id = str(uuid.uuid4())
        directory = self.base_dir / doc_id
        directory.mkdir(parents=True, exist_ok=True)
        target_file = directory / f"{ORIGINAL_FILE_STEM}{suffix}"

        shutil.copy(file_path, target_file)

        doc = Document(
            id=doc_id,
            name=display_name,
            directory=directory,
            original_suffix=suffix,
        )
        self.save_metadata(doc)
        return doc

    def delete(self, doc: Document):
        """Удаляет документ из системы."""
        if doc.directory.exists() and doc.directory.is_dir():
            shutil.rmtree(doc.directory)

    def rename(self, doc: Document, new_name: str):
        """Меняет только отображаемое имя в meta.json (каталог и файлы не переименовываются)."""
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("Имя документа не может быть пустым")

        if new_name == doc.name:
            return

        doc.name = new_name
        self.save_metadata(doc)

    def reload_metadata(self, doc: Document) -> bool:
        """Обновляет данные уже существующего объекта Document данными из метафайла."""
        directory = doc.directory
        meta = self._load_meta(directory)
        if not meta:
            return False

        valid = self._is_directory_valid(directory, meta)
        if not valid:
            return False

        doc.id = meta["id"]
        doc.name = meta.get("name") or ""
        doc.directory = directory
        doc.original_suffix = meta["original_suffix"]
        self._apply_meta_to_document(doc, meta)
        self._resolve_doc_class_to_template_id(doc)
        return True

    def is_file_exists(self, file_path: Path) -> bool:
        """Проверяет, существует ли в системе документ с тем же содержимым исходного файла."""
        if not file_path.is_file():
            return False

        h = self._compute_hash(file_path)
        for doc in self.list():
            p = doc.original_file_path()
            if p.is_file() and self._compute_hash(p) == h:
                return True
        return False

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

    def _get_directory(self, obj: Document) -> Path:
        return obj.directory

    def _is_directory_valid(self, directory: Path, meta: Optional[dict]) -> bool:
        """Проверяет структуру каталога документа в актуальном формате."""
        if not meta:
            return False

        doc_id = meta.get("id")
        if not doc_id or doc_id != directory.name:
            return False

        suffix = meta.get("original_suffix")
        if not suffix:
            return False

        original = directory / f"{ORIGINAL_FILE_STEM}{suffix}"
        if not original.is_file():
            return False

        if meta.get("directory") != str(directory):
            meta = dict(meta)
            meta["directory"] = str(directory)

        return True

    @staticmethod
    def _apply_meta_to_document(doc: Document, meta: dict):
        """Заполняет поля DTO документа из словаря meta.json."""
        doc.status = Document.Status(meta.get("status", Document.Status.UPLOADED))
        doc.doc_class = meta.get("doc_class")
        doc.pipeline_failed_target = DocumentManager._str_status_to_status(meta.get("pipeline_failed_target"))
        doc.pipeline_error_message = meta.get("pipeline_error_message")

    @staticmethod
    def _str_status_to_status(status: str) -> Optional[Document.Status]:
        try:
            return Document.Status(status)
        except ValueError:
            return None

    def _resolve_doc_class_to_template_id(self, doc: Document) -> None:
        """Если в meta сохранено старое значение doc_class (имя шаблона), заменяем на ID шаблона."""
        if not doc.doc_class:
            return
        from app.context import get_temp_manager

        tm = get_temp_manager()
        if tm.get(doc.doc_class):
            return
        for t in tm.list():
            if t.name == doc.doc_class:
                doc.doc_class = t.id
                self.save_metadata(doc)
                return
