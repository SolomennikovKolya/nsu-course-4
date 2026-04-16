from pathlib import Path
from typing import Dict, Optional, Tuple
import mammoth
from html import escape
from docx import Document as DocxDocument
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from core.document import Document


def _docx_to_html_fragment(path: Path) -> str:
    with path.open("rb") as f:
        result = mammoth.convert_to_html(f)
    return result.value


def _wrap_original_html(body_fragment: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{
    font-family: "Segoe UI", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    color: #ffffff;
  }}
  body, p, li, td, th, div, span, strong, em {{ color: #ffffff; }}
  a {{ color: #a8d4ff; }}
  table {{ border-collapse: collapse; margin: 0.5em 0; }}
  td, th {{ border: 1px solid #888888; padding: 4px 6px; vertical-align: top; }}
  p {{ margin: 0.25em 0; }}
</style>
</head>
<body>{body_fragment}</body>
</html>"""


class DocumentViewOriginalTab(QWidget):
    """Вкладка для отображения оригинального документа."""

    def __init__(self):
        super().__init__()
        self._document: Optional[Document] = None
        self._pool = QThreadPool.globalInstance()
        self._request_id = 0
        # cache_key: (abs_path, mtime_ns) -> (mode, content)
        self._cache: Dict[Tuple[str, int], Tuple[str, str]] = {}

        self._docx_bar = QWidget()
        docx_bar_layout = QVBoxLayout(self._docx_bar)
        docx_bar_layout.setContentsMargins(0, 0, 0, 8)

        disclaimer = QLabel(" Предпросмотр документа может отличаться от реального вида документа")
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("QLabel { color: #8a8a8a; }")

        self._open_word_btn = QPushButton("Посмотреть в Word")
        self._open_word_btn.clicked.connect(self._open_original_in_word)

        docx_bar_layout.addWidget(disclaimer)
        docx_bar_layout.addWidget(self._open_word_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._view = QTextBrowser()
        self._view.setReadOnly(True)
        self._view.setOpenExternalLinks(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._docx_bar)
        layout.addWidget(self._view, 1)
        self._docx_bar.setVisible(False)

    def set_document(self, document: Optional[Document]) -> bool:
        self._document = document
        self._view.clear()
        self._view.setPlaceholderText("")
        self._docx_bar.setVisible(False)

        path = self._original_path()
        if path is None:
            self._view.setPlaceholderText("Документ не выбран")
            return False
        if not path.exists():
            self._view.setPlaceholderText("Оригинальный файл документа отсутствует")
            return False

        ext = path.suffix.lower()
        if ext == ".docx":
            self._docx_bar.setVisible(True)
            self._open_word_btn.setEnabled(True)
            cache_key = self._cache_key(path)
            cached = self._cache.get(cache_key) if cache_key is not None else None
            if cached is not None:
                mode, content = cached
                self._apply_preview(mode, content)
                return True

            # Дорого: строим предпросмотр в фоне, UI не блокируем.
            self._view.setPlainText("Загрузка предпросмотра…")
            self._request_id += 1
            req_id = self._request_id
            worker = _DocxPreviewWorker(req_id=req_id, path=path)
            worker.signals.finished.connect(self._on_preview_ready)
            self._pool.start(worker)
            self._docx_bar.setVisible(True)
            self._open_word_btn.setEnabled(True)
            return True

        if ext == ".doc":
            self._view.setPlainText(
                "Предпросмотр файлов формата .doc (Word 97–2003) не поддерживается.\n"
                "Откройте документ во внешнем приложении или сохраните копию в .docx."
            )
            return True

        self._view.setPlainText(
            f"Предпросмотр для формата «{ext or '(нет расширения)'}» не поддерживается."
        )
        return True

    def _original_path(self) -> Optional[Path]:
        if self._document is None:
            return None
        return self._document.original_file_path()

    def _open_original_in_word(self):
        path = self._original_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _cache_key(self, path: Path) -> Optional[Tuple[str, int]]:
        try:
            st = path.stat()
        except OSError:
            return None
        return str(path.resolve()), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))

    def _on_preview_ready(self, req_id: int, mode: str, content: str, cache_key: Optional[Tuple[str, int]]):
        # Если пользователь уже переключился на другой документ — игнорируем.
        if req_id != self._request_id:
            return
        if cache_key is not None:
            self._cache[cache_key] = (mode, content)
        self._apply_preview(mode, content)

    def _apply_preview(self, mode: str, content: str):
        if mode == "html":
            self._view.setHtml(content)
        else:
            self._view.setPlainText(content)


class _DocxPreviewSignals(QObject):
    finished = Signal(int, str, str, object)  # req_id, mode, content, cache_key


class _DocxPreviewWorker(QRunnable):
    def __init__(self, req_id: int, path: Path):
        super().__init__()
        self.req_id = req_id
        self.path = path
        self.signals = _DocxPreviewSignals()

    def run(self):
        cache_key: Optional[Tuple[str, int]]
        try:
            st = self.path.stat()
            cache_key = (str(self.path.resolve()), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
        except OSError:
            cache_key = None

        try:
            fragment = _docx_to_html_fragment(self.path)
            html = _wrap_original_html(fragment)
            self.signals.finished.emit(self.req_id, "html", html, cache_key)
            return
        except Exception as exc:
            try:
                docx = DocxDocument(str(self.path))
                lines = [p.text for p in docx.paragraphs]
                plain = "\n".join(lines)
                note = (
                    "Не удалось показать форматированный предпросмотр "
                    f"({exc}). Ниже — только текст параграфов.\n\n"
                )
                self.signals.finished.emit(self.req_id, "plain", note + plain, cache_key)
                return
            except Exception as exc2:
                html = (
                    "<p style='color:#ff8a80;'>Не удалось открыть DOCX.</p>"
                    f"<pre style='color:#eeeeee;'>{escape(str(exc2))}</pre>"
                )
                self.signals.finished.emit(self.req_id, "html", html, cache_key)
