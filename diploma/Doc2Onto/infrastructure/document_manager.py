import json
import shutil
import hashlib
from pathlib import Path
from dataclasses import asdict
from typing import List, Optional

from core.document.document import Document
from core.document.status import DocumentStatus

BASE_DIR = Path("data/documents")
META_FILENAME = "meta.json"


class DocumentManager:
    """Менеджер для управления документами в файловой системе."""

    def __init__(self, base_dir: Path = BASE_DIR):
        self.base_dir: Path = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # Вспомогательные методы
    # -------------------------

    def _meta_path(self, directory: Path) -> Path:
        return directory / META_FILENAME

    def _compute_hash(self, path: Path) -> str:
        """Вычисляет SHA256 файла."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

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

    def _document_from_meta(self, directory: Path) -> Optional["Document"]:
        meta = self._load_meta(directory)
        if not meta:
            return None

        return Document(
            name=meta.get("name", directory.name),
            directory=directory,
            status=DocumentStatus(meta.get("status", DocumentStatus.UPLOADED)),
            doc_type=meta.get("doc_type"),
            uddm_file=Path(meta["uddm_file"]) if meta.get("uddm_file") else None,
            rdf_file=Path(meta["rdf_file"]) if meta.get("rdf_file") else None,
            validated_rdf_file=Path(meta["validated_rdf_file"]) if meta.get("validated_rdf_file") else None,
        )

    # -------------------------
    # Публичные методы
    # -------------------------

    def list_documents(self) -> List["Document"]:
        """Возвращает список всех документов."""

        docs: List["Document"] = []
        if not self.base_dir.exists():
            return docs

        for directory in self.base_dir.iterdir():
            if directory.is_dir():
                doc = self._document_from_meta(directory)
                if doc:
                    docs.append(doc)

        return docs

    def get(self, name: str) -> Optional["Document"]:
        """Возвращает один документ по имени."""

        directory = self.base_dir / name
        if not directory.exists():
            return None

        return self._document_from_meta(directory)

    def add(self, file_path: Path) -> "Document":
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
            directory=directory
        )
        self.save_metadata(doc)

        return doc

    def save_metadata(self, document: "Document"):
        """Сохраняет метаданные документа."""

        data = asdict(document)

        # Path -> str
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)

        self._save_meta(document.directory, data)
