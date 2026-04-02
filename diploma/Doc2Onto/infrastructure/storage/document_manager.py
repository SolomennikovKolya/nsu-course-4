import shutil
from pathlib import Path
from typing import Optional, Tuple

from app.context import get_temp_manager, get_logger
from core.document import Document
from core.uddm import UDDM
from infrastructure.storage.base_manager import BaseManager

BASE_DIR = Path("data/documents")


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

    def __init__(self, base_dir: Path = BASE_DIR):
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
            doc_class=meta.get("doc_class")
        )

        if doc.uddm_file_path().exists():
            try:
                doc.uddm = UDDM.load(doc.uddm_file_path())
            except Exception as e:
                doc.status = max(doc.status, Document.Status.UPLOADED)
                get_logger().error(f"[DocumentManager] Cannot load UDDM for document {doc.name}: {e}")

        if doc.doc_class:
            doc.template = get_temp_manager().get(doc.doc_class)
            if not doc.template:
                doc.status = max(doc.status, Document.Status.UDDM_EXTRACTED)
                doc.doc_class = None
                get_logger().warning(
                    f"[DocumentManager] Document {doc.name} has class {doc.doc_class} but no corresponding template found")

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
