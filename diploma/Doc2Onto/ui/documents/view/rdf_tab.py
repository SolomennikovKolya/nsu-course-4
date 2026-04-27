from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from models.document import Document


class DocumentViewRdfTab(QWidget):
    def __init__(self):
        super().__init__()
        self._label = QLabel("")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def set_document(self, document: Optional[Document]) -> bool:
        if document is None:
            self._label.setText("")
            return False
        self._label.setText("Пока не поддерживается")
        return False
