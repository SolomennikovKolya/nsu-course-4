from dataclasses import dataclass
from core.status import DocumentStatus


@dataclass
class Document:
    name: str
    path: str
    status: DocumentStatus = DocumentStatus.UPLOADED
