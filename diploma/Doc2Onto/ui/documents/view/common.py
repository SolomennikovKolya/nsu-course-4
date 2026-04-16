from pathlib import Path
from PySide6.QtWidgets import QVBoxLayout, QWidget


def wrap_tab_page_content(inner: QWidget) -> QWidget:
    """Вкладывает виджет страницы вкладки в layout с отступами."""
    outer = QWidget()
    layout = QVBoxLayout(outer)
    layout.setContentsMargins(4, 8, 4, 8)
    layout.setSpacing(0)
    layout.addWidget(inner)
    return outer


def read_text_file(path: Path) -> str:
    """Читает текстовый файл и возвращает его содержимое."""
    if not path.exists():
        return ""

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
