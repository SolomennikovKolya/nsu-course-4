import shutil
from pathlib import Path
from typing import Optional

from core.document.document import Document
from core.document.status import DocumentStatus
from infrastructure.storage.base_manager import BaseManager

BASE_DIR = Path("data/documents")


class DocumentManager(BaseManager[Document, Path]):
    """
    Менеджер для управления документами в файловой системе.

    Предполагается, что каждый документ хранится в отдельной директории внутри BASE_DIR, 
    название которой соответствует имени документа. Внутри директории документа должен быть 
    оригинальный файл (имя которого совпадает с названием директории) и файл meta.json с метаданными документа.
    Также в этой директории хранятся промежуточные файлы обработки документа.

    BASE_DIR
    └── document_i.docx/
        ├── meta.json
        ├── document_i.docx
        ├── uddm.xml
        ├── rdf.xml
        └── validated_rdf.xml
    """

    def __init__(self, base_dir: Path = BASE_DIR):
        super().__init__(base_dir)

    def _get_directory(self, obj: Document) -> Path:
        return obj.directory

    def _object_from_meta(self, directory: Path) -> Optional[Document]:
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

    def add(self, file_path: Path) -> Document:
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

        doc = Document(name=name, directory=directory, original_file=target_file)
        self.save_metadata(doc)
        return doc
