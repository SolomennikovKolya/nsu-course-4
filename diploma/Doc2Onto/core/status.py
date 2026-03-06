from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "Uploaded"
    PROCESSED = "Processed"
