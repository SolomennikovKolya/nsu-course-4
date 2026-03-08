import json
import shutil
import hashlib
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict

from core.document.document import Document
from core.document.status import DocumentStatus

BASE_DIR = Path("data/documents")
META_FILENAME = "meta.json"


class DocumentManager:
    """
    Менеджер для управления документами в файловой системе.

    Предполагается, что каждый документ хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени документа. Внутри директории документа должен быть 
    оригинальный файл (имя которого совпадает с названием директории) и файл meta.json с метаданными документа.
    Также в этой директории хранятся промежуточные файлы обработки документа.

    Пример структуры:
    BASE_DIR
    └── document_i.docx/
        ├── meta.json
        ├── document_i.docx
        ├── uddm.xml
        ├── rdf.xml
        └── validated_rdf.xml
    """

    def __init__(self, base_dir: Path = BASE_DIR):
        self.base_dir: Path = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, path: Path) -> str:
        """Вычисляет SHA256 файла."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _meta_path(self, directory: Path) -> Path:
        return directory / META_FILENAME

    def _load_meta(self, directory: Path) -> dict:
        meta_file = self._meta_path(directory)
        if not meta_file.exists():
            return {}
        with meta_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_meta(self, directory: Path, data: dict):
        meta_file = self._meta_path(directory)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _document_from_meta(self, directory: Path) -> Optional[Document]:
        """Десериализует объект Document из метаданных в директории."""
        meta = self._load_meta(directory)

        # Если оригинальный файл существует, но мета нет — создаем мета по умолчанию
        # Если оригинального файла нет, то и документ не существует, даже если мета есть (битая мета)
        name = meta.get("name", directory.name)
        original_file = Path(meta["original_file"]) if meta.get("original_file") else directory / name
        if not original_file.exists():
            return None

        return Document(
            name=name,
            directory=directory,
            original_file=original_file,
            status=DocumentStatus(meta.get("status", DocumentStatus.UPLOADED)),
            doc_class=meta.get("doc_class"),
            uddm_file=Path(meta["uddm_file"]) if meta.get("uddm_file") else None,
            rdf_file=Path(meta["rdf_file"]) if meta.get("rdf_file") else None,
            validated_rdf_file=Path(meta["validated_rdf_file"]) if meta.get("validated_rdf_file") else None,
        )

    def list_documents(self) -> List[Document]:
        """Возвращает список всех документов."""
        docs = []
        if not self.base_dir.exists():
            return docs

        for directory in self.base_dir.iterdir():
            if not directory.is_dir():
                continue

            doc = self._document_from_meta(directory)
            if doc:
                docs.append(doc)

        return docs

    def get(self, name: str) -> Optional[Document]:
        """Возвращает один документ по имени."""
        directory = self.base_dir / name
        return self._document_from_meta(directory) if directory.exists() else None

    def add(self, file_path: Path) -> Document:
        """Добавляет новый документ. Если файл уже есть в системе и совпадает — ничего не делает."""
        name = file_path.name
        directory = self.base_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        target_file = directory / name

        if target_file.exists():
            if self._compute_hash(target_file) == self._compute_hash(file_path):
                doc = self.get(name)
                if doc:
                    return doc

        shutil.copy(file_path, target_file)

        doc = Document(
            name=name,
            directory=directory,
            original_file=target_file
        )
        self.save_metadata(doc)

        return doc

    def save_metadata(self, document: Document):
        """Сохраняет метаданные документа."""
        data = asdict(document)

        # Path -> str
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        self._save_meta(document.directory, data)
