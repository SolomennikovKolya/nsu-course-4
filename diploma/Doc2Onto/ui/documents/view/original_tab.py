"""
Вкладка «Оригинал»: предпросмотр PDF, DOCX и DOC через единый рендер QtPdf.

DOC/DOCX конвертируются в PDF локально (LibreOffice soffice; на Windows при
отсутствии LO — экспорт через Word COM), без сетевых API. Кэш: ``<stem>.preview.pdf``
рядом с исходным файлом; пересборка при изменении исходника (и рядом лежащего .docx для .doc).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.document import Document
from modules.converter.normalizers.doc_to_docx import DocToDocx
from ui.common.design import UI_COLOR_RED

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    _QT_PDF = True
except ImportError:
    QPdfDocument = None  # type: ignore[misc, assignment]
    QPdfView = None  # type: ignore[misc, assignment]
    _QT_PDF = False


_PREVIEW_SUFFIX = ".preview.pdf"


def _mtime_ns(path: Path) -> Optional[int]:
    try:
        st = path.stat()
    except OSError:
        return None
    return int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))


def _preview_cache_path(source: Path) -> Path:
    return source.with_name(source.stem + _PREVIEW_SUFFIX)


def _libreoffice_candidates() -> List[Path]:
    return DocToDocx()._libreoffice_candidates()


def _run_soffice_convert_to_pdf(exe: Path, src: Path, out_dir: Path) -> bool:
    src_abs = str(src.resolve())
    out_abs = str(out_dir.resolve())
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        subprocess.run(
            [str(exe), "--headless", "--convert-to", "pdf", "--outdir", out_abs, src_abs],
            check=True,
            capture_output=True,
            timeout=300,
            creationflags=creationflags,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    produced = out_dir / (src.stem + ".pdf")
    return produced.is_file()


def _convert_with_libreoffice_to_path(src: Path, dest_pdf: Path) -> bool:
    for exe in _libreoffice_candidates():
        if not exe.is_file():
            continue
        tmp = Path(tempfile.mkdtemp(prefix="doc2onto_pdf_"))
        try:
            if not _run_soffice_convert_to_pdf(exe, src, tmp):
                continue
            produced = tmp / (src.stem + ".pdf")
            if not produced.is_file():
                continue
            dest_pdf.parent.mkdir(parents=True, exist_ok=True)
            try:
                produced.replace(dest_pdf)
            except OSError:
                shutil.copy2(produced, dest_pdf)
            return True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return False


def _convert_with_word_export_pdf(src: Path, dest_pdf: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return False

    wd_export_pdf = 17  # wdExportFormatPDF
    word = None
    doc = None
    tmp_pdf = dest_pdf.with_suffix(".tmp.pdf")
    try:
        if tmp_pdf.is_file():
            tmp_pdf.unlink()
    except OSError:
        pass
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)
        doc.ExportAsFixedFormat(OutputFileName=str(tmp_pdf.resolve()), ExportFormat=wd_export_pdf)
        doc.Close(SaveChanges=False)
        doc = None
        word.Quit()
        word = None
        if not tmp_pdf.is_file():
            return False
        dest_pdf.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_pdf.replace(dest_pdf)
        except OSError:
            shutil.copy2(tmp_pdf, dest_pdf)
            tmp_pdf.unlink(missing_ok=True)
        return True
    except Exception:
        try:
            if doc is not None:
                doc.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            tmp_pdf.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _preview_source_paths(original: Path) -> List[Path]:
    ext = original.suffix.lower()
    if ext == ".pdf":
        return [original]
    if ext == ".docx":
        return [original]
    if ext == ".doc":
        out = [original]
        sidecar = original.with_suffix(".docx")
        if sidecar.is_file():
            out.append(sidecar)
        return out
    return [original]


def _cache_is_fresh(cache: Path, originals: List[Path]) -> bool:
    ct = _mtime_ns(cache)
    if ct is None:
        return False
    for p in originals:
        if not p.is_file():
            return False
        mt = _mtime_ns(p)
        if mt is None or mt > ct:
            return False
    return True


def _ensure_docx_for_doc(doc_path: Path) -> Path:
    docx = doc_path.with_suffix(".docx")
    if docx.is_file():
        doc_mt = _mtime_ns(doc_path)
        docx_mt = _mtime_ns(docx)
        if doc_mt is not None and docx_mt is not None and docx_mt >= doc_mt:
            return docx
    DocToDocx().normalize(doc_path)
    if not docx.is_file():
        raise RuntimeError("Не удалось получить DOCX из DOC для предпросмотра.")
    return docx


def build_or_reuse_preview_pdf(original: Path) -> Path:
    """
    Возвращает путь к PDF для предпросмотра: для .pdf — сам файл; иначе кэш ``<stem>.preview.pdf``.
    """
    ext = original.suffix.lower()
    if ext == ".pdf":
        if not original.is_file():
            raise FileNotFoundError(str(original))
        return original.resolve()

    if ext not in (".docx", ".doc"):
        raise ValueError(f"Неподдерживаемое расширение для предпросмотра: {ext}")

    sources = _preview_source_paths(original)
    dest = _preview_cache_path(original)

    if dest.is_file() and _cache_is_fresh(dest, sources):
        return dest.resolve()

    src_for_lo = original
    if ext == ".doc":
        if _convert_with_libreoffice_to_path(original, dest):
            return dest.resolve()
        if _convert_with_word_export_pdf(original, dest):
            return dest.resolve()
        src_for_lo = _ensure_docx_for_doc(original)

    if not _convert_with_libreoffice_to_path(src_for_lo, dest):
        if not _convert_with_word_export_pdf(src_for_lo, dest):
            raise RuntimeError(
                "Не удалось сделать PDF для предпросмотра. Установите LibreOffice и добавьте "
                "soffice в PATH (или переменную SOFFICE_PATH). На Windows при установленном "
                "Microsoft Word можно экспортировать без LibreOffice."
            )

    if not dest.is_file() or _mtime_ns(dest) is None:
        raise RuntimeError("Конвертация завершилась без выходного PDF.")

    return dest.resolve()


class OriginalPdfPreviewWidget(QWidget):
    """Встроенный просмотр PDF с зумом (отдельный виджет в этом же модуле)."""

    def __init__(self):
        super().__init__()
        self._pdf_view: Optional[QPdfView] = None
        self._pdf_doc: Optional[QPdfDocument] = None

        self._toolbar = QWidget()
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(0, 0, 0, 0)

        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_out.setFixedWidth(32)
        self._zoom_in.setFixedWidth(32)
        self._zoom_out.clicked.connect(self._on_zoom_out)
        self._zoom_in.clicked.connect(self._on_zoom_in)

        self._fit_width = QPushButton("По ширине")
        self._fit_page = QPushButton("По высоте")
        self._fit_width.clicked.connect(self._on_fit_width)
        self._fit_page.clicked.connect(self._on_fit_page)

        # tb.addWidget(QLabel("Масштаб:"))
        tb.addWidget(self._zoom_out)
        tb.addWidget(self._zoom_in)
        tb.addWidget(self._fit_width)
        tb.addWidget(self._fit_page)
        tb.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addWidget(self._toolbar)

        self._toolbar.setEnabled(_QT_PDF)

    def clear(self):
        if self._pdf_view is None:
            return
        self.layout().removeWidget(self._pdf_view)
        self._pdf_view.deleteLater()
        self._pdf_view = None
        self._pdf_doc = None

    def load_pdf(self, path: Path) -> bool:
        self.clear()
        if not _QT_PDF or QPdfView is None or QPdfDocument is None:
            return False

        view = QPdfView()
        doc = QPdfDocument(view)
        view.setDocument(doc)
        doc.load(str(path.resolve()))
        if doc.pageCount() < 1:
            view.deleteLater()
            return False

        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.layout().addWidget(view, 1)
        self._pdf_view = view
        self._pdf_doc = doc
        return True

    def _on_fit_width(self):
        if self._pdf_view is None:
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _on_fit_page(self):
        if self._pdf_view is None:
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)

    def _on_zoom_in(self):
        if self._pdf_view is None:
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(min(5.0, self._pdf_view.zoomFactor() * 1.15))

    def _on_zoom_out(self):
        if self._pdf_view is None:
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(max(0.25, self._pdf_view.zoomFactor() / 1.15))


class _PreviewPdfSignals(QObject):
    finished = Signal(int, str)
    failed = Signal(int, str)


class _PreviewPdfWorker(QRunnable):
    def __init__(self, req_id: int, original: Path, bridge: _PreviewPdfSignals):
        super().__init__()
        self.req_id = req_id
        self.original = original
        self._bridge = bridge

    def run(self):
        # Word/pywin32 и COM Word небезопасны при параллельных вызовах; пул предпросмотра
        # ограничен одним потоком, здесь дополнительно инициализируем COM на этом потоке (Windows).
        com_inited = False
        if os.name == "nt":
            try:
                import pythoncom  # type: ignore[import-untyped]

                pythoncom.CoInitialize()
                com_inited = True
            except Exception:
                pass
        try:
            pdf = build_or_reuse_preview_pdf(self.original)
            self._bridge.finished.emit(self.req_id, str(pdf))
        except Exception as exc:
            self._bridge.failed.emit(self.req_id, str(exc))
        finally:
            if com_inited:
                try:
                    import pythoncom  # type: ignore[import-untyped]

                    pythoncom.CoUninitialize()
                except Exception:
                    pass


class DocumentViewOriginalTab(QWidget):
    """Вкладка для отображения оригинального документа (через PDF-предпросмотр)."""

    def __init__(self):
        super().__init__()
        self._document: Optional[Document] = None
        # Один поток: LibreOffice/Word не должны выполняться параллельно (COM / процессы).
        self._preview_pool = QThreadPool(self)
        self._preview_pool.setMaxThreadCount(1)
        self._request_id = 0

        self._preview_bridge = _PreviewPdfSignals(self)
        self._preview_bridge.finished.connect(
            self._on_preview_pdf_ready,
            Qt.ConnectionType.QueuedConnection,
        )
        self._preview_bridge.failed.connect(
            self._on_preview_pdf_failed,
            Qt.ConnectionType.QueuedConnection,
        )

        self._toolbar = QWidget()
        toolbar_layout = QVBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 8)

        disclaimer = QLabel(
            "Предпросмотр через PDF; для DOC/DOCX вид может слегка отличаться от оригинала."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("QLabel { color: #8a8a8a; }")

        self._open_external_btn = QPushButton()
        self._open_external_btn.clicked.connect(self._open_original_externally)

        # toolbar_layout.addWidget(disclaimer)
        toolbar_layout.addWidget(self._open_external_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._stack = QStackedWidget()
        self._message = QTextBrowser()
        self._message.setReadOnly(True)
        self._message.setOpenExternalLinks(True)
        self._message.setFrameShape(QFrame.Shape.NoFrame)
        self._stack.addWidget(self._message)

        self._pdf_preview = OriginalPdfPreviewWidget()
        self._stack.addWidget(self._pdf_preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._stack, 1)
        self._toolbar.setVisible(False)

    def set_document(self, document: Optional[Document]) -> bool:
        self._document = document
        self._request_id += 1
        req_id = self._request_id

        self._message.clear()
        self._message.setPlaceholderText("")
        self._toolbar.setVisible(False)
        self._stack.setCurrentWidget(self._message)
        self._pdf_preview.clear()

        path = self._original_path()
        if path is None:
            self._message.setPlaceholderText("Документ не выбран")
            return False
        if not path.exists():
            self._message.setPlaceholderText("Оригинальный файл документа отсутствует")
            return False

        ext = path.suffix.lower()
        if ext not in (".pdf", ".docx", ".doc"):
            self._message.setPlainText(
                f"Предпросмотр для формата «{ext or '(нет расширения)'}» не поддерживается."
            )
            return True

        if not _QT_PDF:
            self._message.setPlainText(
                "Встроенный просмотр PDF недоступен: в сборке PySide6 нет модулей QtPdf / QtPdfWidgets."
            )
            return True

        self._toolbar.setVisible(True)
        self._open_external_btn.setText("Открыть оригинал в программе по умолчанию")

        self._message.setPlainText("Подготовка предпросмотра…")
        worker = _PreviewPdfWorker(req_id=req_id, original=path, bridge=self._preview_bridge)
        self._preview_pool.start(worker)
        return True

    def _original_path(self) -> Optional[Path]:
        if self._document is None:
            return None
        return self._document.original_file_path()

    def _on_preview_pdf_ready(self, req_id: int, pdf_path: str):
        if req_id != self._request_id:
            return
        path = Path(pdf_path)
        if self._pdf_preview.load_pdf(path):
            self._stack.setCurrentWidget(self._pdf_preview)
        else:
            self._message.setPlainText("Не удалось открыть PDF для предпросмотра.")
            self._stack.setCurrentWidget(self._message)

    def _on_preview_pdf_failed(self, req_id: int, message: str):
        if req_id != self._request_id:
            return
        self._message.setHtml(
            f"<p style='color:{UI_COLOR_RED};'>Не удалось подготовить предпросмотр.</p>"
            f"<pre style='color:#eeeeee;'>{message}</pre>"
        )
        self._stack.setCurrentWidget(self._message)

    def _open_original_externally(self):
        path = self._original_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
