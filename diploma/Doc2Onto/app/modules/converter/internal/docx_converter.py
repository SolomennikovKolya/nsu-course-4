from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

from core.uddm.uddm import *
from app.modules.converter.internal.base import BaseInternalConverter


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxConverter(BaseInternalConverter):
    """Конвертирует DOCX в объектную модель UDDM."""

    def convert(self, file_path: Path) -> UDDM:
        try:
            with ZipFile(file_path) as docx:
                xml_data = docx.read("word/document.xml")

            root = ET.fromstring(xml_data)
            body = root.find(f"{W}body")
            if body is None:
                raise RuntimeError(f"Cannot find body in DOCX file: {file_path}")

            blocks = self._parse_blocks(body)
            return UDDM(blocks)

        except Exception as e:
            return UDDM([])

    def _parse_blocks(self, parent: ET.Element) -> List[Block]:
        blocks: List[Block] = []
        paragraph_buffer: List[str] = []

        list_stack: List[Tuple[int, int, ListBlock]] = []
        current_list: Optional[ListBlock] = None
        current_item: Optional[Item] = None

        for child in parent:
            tag = child.tag

            if tag == f"{W}p":
                list_info = self._get_list_info(child)

                text = self._extract_paragraph_text(child).strip()
                if not text and not list_info:
                    continue

                # Парсинг списка
                if list_info:
                    if paragraph_buffer:
                        self._append_text(blocks, paragraph_buffer)
                        paragraph_buffer = []

                    list_stack, current_list, current_item = self._handle_list(
                        blocks,
                        list_stack,
                        current_list,
                        current_item,
                        list_info
                    )

                    current_item = Item([Text([P(text)])])
                    current_list.items.append(current_item)

                # Парсинг обычного абзаца
                else:
                    list_stack = []
                    current_list = None
                    current_item = None

                    if text:
                        paragraph_buffer.append(text)

            # Парсинг таблицы
            elif tag == f"{W}tbl":
                if paragraph_buffer:
                    self._append_text(blocks, paragraph_buffer)
                    paragraph_buffer = []

                list_stack = []
                current_list = None
                current_item = None

                table = self._parse_table(child)
                blocks.append(table)

        if paragraph_buffer:
            self._append_text(blocks, paragraph_buffer)

        return blocks

    def _append_text(self, blocks: List, paragraphs: List[str]):
        """Добавляет параграфы к текущим блокам."""
        if not paragraphs:
            return

        # Объединяем идущие подряд параграфы в один текстовый блок
        if blocks and isinstance(blocks[-1], Text):
            for p in paragraphs:
                blocks[-1].paragraphs.append(P(p))
        else:
            blocks.append(Text([P(p) for p in paragraphs]))

    def _handle_list(self, blocks: List[Block], stack: List[Tuple[int, int, ListBlock]],
                     current_list: Optional[ListBlock], current_item: Optional[Item],
                     new_list_info: Tuple[int, int]) -> Tuple[List[Tuple[int, int, ListBlock]], ListBlock, Optional[Item]]:

        num_id, level = new_list_info

        # Если стек пуст — начинаем новый список
        if not stack:
            new_list = ListBlock([])

            blocks.append(new_list)
            stack = [(num_id, level, new_list)]

            return stack, new_list, None

        top_num, top_level, top_list = stack[-1]

        # Новый список (другой numId)
        if num_id != top_num:
            new_list = ListBlock([])
            blocks.append(new_list)

            stack = [(num_id, level, new_list)]

            return stack, new_list, None

        # deeper level
        if level > top_level:
            new_list = ListBlock([])

            if current_item:
                current_item.blocks.append(new_list)

            stack.append((num_id, level, new_list))

            return stack, new_list, None

        # same level
        if level == top_level:
            return stack, top_list, None

        # go up
        while stack and stack[-1][1] > level:
            stack.pop()

        if not stack:
            new_list = ListBlock([])
            blocks.append(new_list)

            stack = [(num_id, level, new_list)]

            return stack, new_list, None

        return stack, stack[-1][2], None

    def _parse_table(self, tbl: ET.Element) -> Table:
        rows = []

        for tr in tbl.findall(f"{W}tr"):
            cells = []
            for tc in tr.findall(f"{W}tc"):
                blocks = self._parse_blocks(tc)
                cells.append(Cell(blocks))

            rows.append(Row(cells))

        return Table(rows)

    def _extract_paragraph_text(self, paragraph: ET.Element) -> str:
        texts = []

        for t in paragraph.findall(f".//{W}t"):
            if t.text:
                texts.append(t.text)

        return "".join(texts)

    def _get_list_info(self, paragraph: ET.Element) -> Optional[Tuple[int, int]]:
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

        int_id = int(num_id.attrib[f"{W}val"])
        int_lvl = int(ilvl.attrib[f"{W}val"]) if ilvl is not None else 0

        return int_id, int_lvl
