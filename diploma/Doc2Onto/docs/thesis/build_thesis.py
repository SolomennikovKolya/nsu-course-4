"""
Сборка ВКР из отдельных Markdown-файлов в единый документ,
готовый для копирования в Microsoft Word.

Что делает:
  1. Читает части ВКР в правильном порядке (аннотация → введение →
     главы → заключение → список литературы → приложения).
  2. Внутри каждого абзаца склеивает строки в одну длинную, чтобы
     при копировании в Word жёсткие переносы строк не превращались
     в отдельные абзацы.
  3. Сохраняет нетронутыми те конструкции, в которых перенос строки
     несёт смысл: кодовые блоки, таблицы, заголовки, элементы списков,
     цитаты, горизонтальные разделители.
  4. По умолчанию убирает вступительные блоки-цитаты (`> …`),
     служившие пометками для рабочего процесса.
  5. Сохраняет результат в `docs/thesis/thesis.md`.

Использование:
  python thesis/build_thesis.py              # сборка с настройками по умолчанию
  python thesis/build_thesis.py --keep-meta  # сохранить вступительные цитаты
  python thesis/build_thesis.py --output FILE.md
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List


# Порядок частей ВКР. Имена файлов относительно директории `docs/thesis/`.
PARTS: List[str] = [
    # "annotation.md",
    "introduction.md",
    "chapter_1.md",
    "chapter_2.md",
    "chapter_3.md",
    "conclusion.md",
    "references.md",
    "appendices.md",
]

THESIS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = THESIS_DIR / "thesis.md"

# Регулярные выражения для распознавания «структурных» строк.
RE_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
RE_HORIZONTAL_RULE = re.compile(r"^\s*(?:---+|___+|\*\*\*+)\s*$")
RE_HEADING = re.compile(r"^\s*#{1,6}\s")
RE_TABLE_LINE = re.compile(r"^\s*\|")
RE_BLOCKQUOTE = re.compile(r"^\s*>")
RE_CODE_FENCE = re.compile(r"^\s*```")


def is_list_item(line: str) -> bool:
    return bool(RE_LIST_MARKER.match(line))


def is_horizontal_rule(line: str) -> bool:
    return bool(RE_HORIZONTAL_RULE.match(line))


def is_heading(line: str) -> bool:
    return bool(RE_HEADING.match(line))


def is_table_line(line: str) -> bool:
    return bool(RE_TABLE_LINE.match(line))


def is_blockquote(line: str) -> bool:
    return bool(RE_BLOCKQUOTE.match(line))


def is_code_fence(line: str) -> bool:
    return bool(RE_CODE_FENCE.match(line))


def unwrap_paragraphs(text: str) -> str:
    """
    Склеивает hard-wrapped строки внутри абзацев в одну длинную строку.

    Не трогает: кодовые блоки, таблицы, заголовки, цитаты, горизонтальные
    разделители. Каждый пункт списка (включая многострочные) превращается
    в одну строку.
    """
    lines = text.split("\n")
    out: List[str] = []
    in_code_block = False
    paragraph_buf: List[str] = []

    def flush_paragraph():
        if not paragraph_buf:
            return
        joined = " ".join(s.strip() for s in paragraph_buf if s.strip())
        if joined:
            out.append(joined)
        paragraph_buf.clear()

    for raw in lines:
        line = raw.rstrip()

        # Кодовые блоки переносим как есть.
        if is_code_fence(line):
            flush_paragraph()
            out.append(line)
            in_code_block = not in_code_block
            continue
        if in_code_block:
            out.append(line)
            continue

        # Пустая строка — конец абзаца.
        if not line.strip():
            flush_paragraph()
            out.append("")
            continue

        # Заголовки, таблицы, цитаты, горизонтальные разделители —
        # выводим построчно, без склейки.
        if (is_heading(line)
                or is_table_line(line)
                or is_blockquote(line)
                or is_horizontal_rule(line)):
            flush_paragraph()
            out.append(line)
            continue

        # Начало нового пункта списка — закрываем предыдущий и
        # начинаем новый «абзац-пункт».
        if is_list_item(line):
            flush_paragraph()
            paragraph_buf.append(line)
            continue

        # Обычная строка: продолжение текущего абзаца или пункта списка.
        paragraph_buf.append(line)

    flush_paragraph()

    # Сжатие подряд идущих пустых строк до одной.
    collapsed: List[str] = []
    prev_empty = False
    for line in out:
        empty = not line.strip()
        if empty and prev_empty:
            continue
        collapsed.append(line)
        prev_empty = empty

    return "\n".join(collapsed).strip() + "\n"


def strip_meta_blockquotes(text: str) -> str:
    """
    Убирает блок-цитат, идущий в самом начале файла. Это пометки для
    рабочего процесса (например, "Список оформлен в стиле…"), не
    предназначенные для финального текста ВКР.
    """
    lines = text.split("\n")
    i = 0
    # Пропускаем пустые строки.
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Пропускаем заголовок (если первая значимая строка — заголовок).
    if i < len(lines) and is_heading(lines[i]):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    # Если за заголовком идёт блок-цитата — выкусываем её.
    if i < len(lines) and is_blockquote(lines[i]):
        start_quote = i
        while i < len(lines) and (is_blockquote(lines[i]) or not lines[i].strip()):
            i += 1
        end_quote = i
        return "\n".join(lines[:start_quote] + lines[end_quote:])
    return text


def read_part(path: Path, *, strip_meta: bool) -> str:
    text = path.read_text(encoding="utf-8")
    if strip_meta:
        text = strip_meta_blockquotes(text)
    text = unwrap_paragraphs(text)
    return text.rstrip() + "\n"


def build(output: Path, *, strip_meta: bool):
    chunks: List[str] = []
    for name in PARTS:
        path = THESIS_DIR / name
        if not path.exists():
            print(f"[!] Пропущено (файл не найден): {path}")
            continue
        chunks.append(read_part(path, strip_meta=strip_meta))
        print(f"[+] {name}")

    # Между частями — пустая строка. Дополнительные разделители не нужны:
    # каждая часть начинается с собственного заголовка верхнего уровня.
    full = "\n\n".join(chunks).rstrip() + "\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(full, encoding="utf-8")

    size_kb = output.stat().st_size / 1024
    line_count = full.count("\n")
    print()
    print(f"Сохранено в {output}")
    print(f"  размер: {size_kb:.1f} КБ")
    print(f"  строк:  {line_count}")
    print()
    print("Дальнейшие шаги для переноса в Word:")
    print("  1. Открыть собранный файл в любом текстовом редакторе.")
    print("  2. Выделить всё содержимое и скопировать (Ctrl+A, Ctrl+C).")
    print("  3. Вставить в Word через 'Сохранить только текст' (Ctrl+Shift+V).")
    print("  4. Применить стили заголовков и оформления по требованиям ВКР.")
    print()
    print("Альтернативно — конвертация в .docx через pandoc:")
    print(f"  pandoc thesis/thesis.md -o thesis/thesis.docx --reference-doc=artifacts/format_ref.docx")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сборка ВКР в единый Markdown-документ для Word.",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Путь к выходному файлу (по умолчанию: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--keep-meta", action="store_true",
        help="Сохранить вступительные блок-цитаты (рабочие пометки) в файлах.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    build(args.output, strip_meta=not args.keep_meta)


if __name__ == "__main__":
    main()
