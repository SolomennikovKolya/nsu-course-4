from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

from core.uddm.model import UDDM, Block, Text, P, ListBlock, Item, Table, Row, Cell
from modules.converter.internal.base import BaseInternalConverter


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxConverter(BaseInternalConverter):
    """Конвертирует DOCX в объектную модель UDDM."""

    def convert(self, file_path: Path) -> UDDM:
        try:
            with ZipFile(file_path) as docx:
                body = self._load_document_body(docx)
                self.styles = self._load_styles(docx)

            blocks = self._parse_blocks(body)
            return UDDM(blocks)

        except Exception:
            return UDDM([])

    def _load_document_body(self, docx: ZipFile) -> ET.Element:
        """
        Загружает и парсит основной XML документа, возвращая элемент body.
        Может выкинуть исключение.
        """
        try:
            xml_data = docx.read("word/document.xml")
        except KeyError:
            raise RuntimeError("DOCX document.xml не найден")

        root = ET.fromstring(xml_data)

        body = root.find(f"{W}body")
        if body is None:
            raise RuntimeError("DOCX body не найден")

        return body

    def _load_styles(self, docx: ZipFile) -> dict:
        """
        Загружает стили из DOCX и возвращает словарь вида {style_id: style_name}. 
        Это нужно для определения заголовков.
        """
        try:
            xml_data = docx.read("word/styles.xml")
        except KeyError:
            return {}

        root = ET.fromstring(xml_data)

        styles = {}

        for style in root.findall(f"{W}style"):
            style_id = style.attrib.get(f"{W}styleId")
            name_el = style.find(f"{W}name")

            if style_id and name_el is not None:
                name = name_el.attrib.get(f"{W}val", "")
                styles[style_id] = name

        return styles

    def _parse_blocks(self, parent: ET.Element) -> List[Block]:
        """Рекурсивный парсинг блоков из XML-дерева DOCX. Поддерживает параграфы, списки и таблицы."""
        blocks: List[Block] = []
        text_buffer: List[str] = []

        list_stack: List[Tuple[int, int, ListBlock]] = []
        current_item: Optional[Item] = None

        for child in parent:

            if child.tag == f"{W}p":
                text = self._extract_paragraph_text(child).strip()
                list_info = self._get_list_info(child)
                is_heading = self._is_heading(child)

                # Пропускаем пустые параграфы
                if not text and not list_info:
                    continue

                # === список ===
                if list_info and not is_heading:
                    self._flush_text(blocks, text_buffer)

                    list_stack, current_item = self._process_list(
                        blocks,
                        list_stack,
                        current_item,
                        list_info,
                        text
                    )

                # === обычный параграф ===
                else:
                    list_stack = []
                    current_item = None

                    # Заголовок начинает новый блок
                    if is_heading:
                        self._flush_text(blocks, text_buffer)

                    text_buffer.append(text)

            # === таблица ===
            elif child.tag == f"{W}tbl":
                list_stack = []
                current_item = None

                self._flush_text(blocks, text_buffer)

                blocks.append(self._parse_table(child))

        self._flush_text(blocks, text_buffer)

        return blocks

    def _flush_text(self, blocks: List[Block], buffer: List[str]):
        """Выносит накопленный текст в новый блок и очищает буфер."""
        if not buffer:
            return

        paragraphs = [P(t) for t in buffer]
        blocks.append(Text(paragraphs))
        buffer.clear()

    def _process_list(
        self,
        blocks: List[Block],
        stack: List[Tuple[int, int, ListBlock]],
        current_item: Optional[Item],
        list_info: Tuple[int, int],
        text: str
    ) -> Tuple[List[Tuple[int, int, ListBlock]], Item]:
        """
        Обрабатывает элемент списка. Предполагается, что список может содержать текст и вложенные списки, но не таблицы. 
        Возвращает обновлённый стек и текущий элемент списка.
        """
        num_id, level = list_info

        # Новый список
        if not stack or stack[-1][0] != num_id:
            new_list = ListBlock([])
            blocks.append(new_list)

            stack = [(num_id, level, new_list)]

        # Вложенность
        else:
            while stack and stack[-1][1] > level:
                stack.pop()

            if stack and level > stack[-1][1]:
                new_list = ListBlock([])

                if current_item:
                    current_item.blocks.append(new_list)

                stack.append((num_id, level, new_list))

        current_list = stack[-1][2]

        item = Item([Text([P(text)])])
        current_list.items.append(item)

        return stack, item

    def _parse_table(self, tbl: ET.Element) -> Table:
        """Парсинг таблицы. Таблица может содержать любые блоки в ячейках."""
        rows = []

        for tr in tbl.findall(f"{W}tr"):
            cells = []
            for tc in tr.findall(f"{W}tc"):
                blocks = self._parse_blocks(tc)
                cells.append(Cell(blocks))

            rows.append(Row(cells))

        return Table(rows)

    def _extract_paragraph_text(self, paragraph: ET.Element) -> str:
        """Достаёт весь текст из параграфа."""
        texts = []

        for t in paragraph.findall(f".//{W}t"):
            if t.text:
                texts.append(t.text)

        return "".join(texts)

    def _get_list_info(self, paragraph: ET.Element) -> Optional[Tuple[int, int]]:
        """Определяет, является ли параграф элементом списка и возвращает его идентификатор и уровень вложенности."""
        ppr = paragraph.find(f"{W}pPr")
        if ppr is None:
            return None

        numpr = ppr.find(f"{W}numPr")
        if numpr is None:
            return None

        num_id = numpr.find(f"{W}numId")
        ilvl = numpr.find(f"{W}ilvl")

        if num_id is None:
            return None

        num_id = int(num_id.attrib[f"{W}val"])
        level = int(ilvl.attrib[f"{W}val"]) if ilvl is not None else 0

        return num_id, level

    def _is_heading(self, paragraph: ET.Element) -> bool:
        """Определяет, является ли параграф заголовком."""
        ppr = paragraph.find(f"{W}pPr")
        if ppr is None:
            return False

        style = ppr.find(f"{W}pStyle")
        if style is None:
            return False

        style_id = style.attrib.get(f"{W}val")
        if not style_id:
            return False

        if style_id.lower().startswith("heading") or style_id.lower().startswith("заголов"):
            return True

        style_name = self.styles.get(style_id, "")
        name = style_name.lower()

        if "heading" in name or "заголов" in name:
            return True

        return self._is_heading_heuristic(paragraph)

    def _is_heading_heuristic(self, paragraph: ET.Element) -> bool:
        """
        Эвристика для определения заголовков, если стиль не распознан. 
        Предполагает, что заголовки обычно короткие, жирные и/или центрированные.
        """
        text = self._extract_paragraph_text(paragraph).strip()

        if not text:
            return False

        if len(text) > 100:
            return False

        ppr = paragraph.find(f"{W}pPr")
        if ppr is None:
            return False

        rpr = ppr.find(f"{W}rPr")
        if rpr is None:
            return False

        is_bold = rpr.find(f"{W}b") is not None

        jc = ppr.find(f"{W}jc")
        is_center = jc is not None and jc.attrib.get(f"{W}val") == "center"

        return is_bold and is_center
