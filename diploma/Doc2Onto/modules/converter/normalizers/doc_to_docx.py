"""
Преобразование legacy .doc → .docx через внешние движки (без собственного разбора OLE).

Порядок попыток:
1. LibreOffice в headless-режиме (``soffice`` / ``libreoffice`` или путь из ``SOFFICE_PATH``).
2. Только Windows: Microsoft Word через COM (если установлен Word и пакет ``pywin32``).

Результат — ``.docx`` рядом с исходным файлом (то же имя, расширение ``.docx``).

Требуется установленный LibreOffice и/или Word; иначе ``normalize`` завершится ошибкой с пояснением.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from modules.converter.normalizers.base import BaseNormalizer


class DocToDocx(BaseNormalizer):
    """Нормализатор: бинарный Word .doc → .docx для последующей обработки ``DocxToUDDM``."""

    target_format = "docx"

    def normalize(self, file_path: Path) -> Path:
        if file_path.suffix.lower() != ".doc":
            raise ValueError(f"Ожидался файл .doc, получено: {file_path}")

        dest = file_path.with_suffix(".docx")
        parent = file_path.parent

        if self._convert_with_libreoffice(file_path, parent):
            if dest.is_file():
                return dest

        if self._convert_with_word_com(file_path, dest):
            if dest.is_file():
                return dest

        raise RuntimeError(
            "Не удалось преобразовать .doc в .docx. Установите LibreOffice "
            "(https://www.libreoffice.org/) и добавьте его в PATH, либо задайте переменную "
            "окружения SOFFICE_PATH к исполняемому файлу soffice. "
            "На Windows при установленном Microsoft Word можно установить пакет pywin32."
        )

    def _libreoffice_candidates(self) -> List[Path]:
        candidates: List[Path] = []
        env = os.environ.get("SOFFICE_PATH")
        if env:
            candidates.append(Path(env))
        for name in ("soffice", "libreoffice"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
        if os.name == "nt":
            for base in (
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            ):
                root = Path(base)
                candidates.append(root / "LibreOffice" / "program" / "soffice.exe")
                for child in sorted(root.glob("LibreOffice *"), reverse=True):
                    candidates.append(child / "program" / "soffice.exe")
        seen: set[str] = set()
        unique: List[Path] = []
        for p in candidates:
            if not p.is_file():
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        return unique

    def _convert_with_libreoffice(self, src: Path, out_dir: Path) -> bool:
        src_abs = str(src.resolve())
        out_abs = str(out_dir.resolve())
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        dest = src.with_suffix(".docx")

        for exe in self._libreoffice_candidates():
            if not exe.is_file():
                continue
            try:
                subprocess.run(
                    [str(exe), "--headless", "--convert-to", "docx", "--outdir", out_abs, src_abs],
                    check=True,
                    capture_output=True,
                    timeout=300,
                    creationflags=creationflags,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
            if dest.is_file():
                return True
        return False

    def _convert_with_word_com(self, src: Path, dest: Path) -> bool:
        if os.name != "nt":
            return False
        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError:
            return False

        wd_format_xml_document = 12  # wdFormatXMLDocument (.docx без макросов)

        word = None
        doc = None
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)
            doc.SaveAs2(str(dest.resolve()), FileFormat=wd_format_xml_document)
            doc.Close(SaveChanges=False)
            doc = None
            word.Quit()
            word = None
            return dest.is_file()
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
            return False
