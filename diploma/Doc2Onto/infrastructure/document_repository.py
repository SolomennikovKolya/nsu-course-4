import os
import shutil
from core.document import Document

BASE_DIR = "data/documents"


class DocumentRepository:

    @staticmethod
    def save(file_path: str) -> Document:
        os.makedirs(BASE_DIR, exist_ok=True)

        name = os.path.basename(file_path)
        target_dir = os.path.join(BASE_DIR, name)

        os.makedirs(target_dir, exist_ok=True)

        target_file = os.path.join(target_dir, name)
        shutil.copy(file_path, target_file)

        return Document(name=name, path=target_file)

    @staticmethod
    def list_documents():
        if not os.path.exists(BASE_DIR):
            return []

        docs = []
        for folder in os.listdir(BASE_DIR):
            folder_path = os.path.join(BASE_DIR, folder)
            if os.path.isdir(folder_path):
                file_path = os.path.join(folder_path, folder)
                if os.path.exists(file_path):
                    docs.append(Document(name=folder, path=file_path))
        return docs
