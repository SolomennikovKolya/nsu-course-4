from __future__ import annotations
from typing import Iterator
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List
from abc import ABC, abstractmethod


class UDDM:
    """Объектная модель документа в формате UDDM."""

    def __init__(self, blocks: List[Block]):
        """
        Пример создания:
        doc = UDDM([
            Text([
                P("Paragraph 1"),
                P("Paragraph 2")
            ])
        ])
        """
        self.blocks: List[Block] = blocks

    def iter_blocks(self) -> Iterator[Block]:
        """Базовый итератор для DFS обхода всех блоков."""
        for block in self.blocks:
            yield from self._iter_block(block)

    def _iter_block(self, block: Block) -> Iterator[Block]:
        yield block

        if isinstance(block, Text):
            return

        elif isinstance(block, ListBlock):
            for item in block.items:
                for b in item.blocks:
                    yield from self._iter_block(b)

        elif isinstance(block, Table):
            for row in block.rows:
                for cell in row.cells:
                    for b in cell.blocks:
                        yield from self._iter_block(b)

    def iter_texts(self) -> Iterator["Text"]:
        """Итератор для обхода всех текстовых блоков."""
        for block in self.iter_blocks():
            if isinstance(block, Text):
                yield block

    def iter_paragraphs(self) -> Iterator["P"]:
        """Итератор для обхода всех абзацев."""
        for text in self.iter_texts():
            for p in text.paragraphs:
                yield p

    def iter_lists(self) -> Iterator["ListBlock"]:
        """Итератор для обхода всех списков."""
        for block in self.iter_blocks():
            if isinstance(block, ListBlock):
                yield block

    def iter_tables(self) -> Iterator["Table"]:
        """Итератор для обхода всех таблиц."""
        for block in self.iter_blocks():
            if isinstance(block, Table):
                yield block

    def get_all_texts(self) -> List[Text]:
        """Получить все текстовые блоки."""
        return [text for text in self.iter_texts()]

    def get_all_paragraphs(self) -> List[P]:
        """Получить все абзацы."""
        return [p for p in self.iter_paragraphs()]

    def get_all_texts_from_paragraphs(self) -> List[str]:
        """Получить все абзацы в виде списка строк."""
        return [str(p) for p in self.iter_paragraphs()]

    def get_all_lists(self) -> List[ListBlock]:
        """Получить все списки."""
        return [lst for lst in self.iter_lists()]

    def get_all_tables(self) -> List[Table]:
        """Получить все таблицы."""
        return [table for table in self.iter_tables()]

    def save(self, path: Path):
        """Сериализация в xml-файл."""
        tree = ET.ElementTree(self._to_xml())
        tree.write(path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def load(path: Path) -> "UDDM":
        """Десериализация из xml-файла."""
        tree = ET.parse(path)
        root = tree.getroot()

        blocks = []
        for child in root:
            blocks.append(Block._from_xml(child))

        return UDDM(blocks)

    def _to_xml(self) -> ET.Element:
        root = ET.Element("document")

        for block in self.blocks:
            root.append(block._to_xml())

        return root


class Block(ABC):
    """Абстрактный базовый блок UDDM."""

    @abstractmethod
    def _to_xml(self) -> ET.Element:
        raise NotImplementedError

    @staticmethod
    def _from_xml(element: ET.Element) -> "Block":
        tag = element.tag

        if tag == "text":
            return Text._from_xml(element)

        if tag == "list":
            return ListBlock._from_xml(element)

        if tag == "table":
            return Table._from_xml(element)

        raise ValueError(f"Unknown block type: {tag}")


class Text(Block):
    """Текстовый блок, состоящий из параграфов."""

    def __init__(self, paragraphs: List[P]):
        self.paragraphs: List[P] = paragraphs

    def __iter__(self):
        return iter(self.paragraphs)

    def __str__(self):
        return "\n".join(str(p) for p in self.paragraphs)

    def __len__(self):
        return len(self.paragraphs)

    def __getitem__(self, index):
        return self.paragraphs[index]

    def _to_xml(self) -> ET.Element:
        el = ET.Element("text")

        for p in self.paragraphs:
            el.append(p._to_xml())

        return el

    @staticmethod
    def _from_xml(element: ET.Element) -> "Text":
        paragraphs = []

        for p in element.findall("p"):
            paragraphs.append(P._from_xml(p))

        return Text(paragraphs)


class P:
    """Параграф - атомарный элемент текста."""

    def __init__(self, text: str):
        self.text: str = text

    def __iter__(self):
        return iter(self.text)

    def __str__(self):
        return self.text

    def __len__(self):
        return len(self.text)

    def __getitem__(self, index):
        return self.text[index]

    def _to_xml(self) -> ET.Element:
        el = ET.Element("p")
        el.text = self.text
        return el

    @staticmethod
    def _from_xml(element: ET.Element) -> "P":
        return P(element.text or "")


class ListBlock(Block):
    """Список."""

    def __init__(self, items: List[Item]):
        self.items: List[Item] = items

    def __iter__(self):
        return iter(self.items)

    def __str__(self):
        return "\n".join(str(p) for p in self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def _to_xml(self) -> ET.Element:
        el = ET.Element("list")

        for item in self.items:
            el.append(item._to_xml())

        return el

    @staticmethod
    def _from_xml(element: ET.Element) -> "ListBlock":
        items = []

        for item_el in element.findall("item"):
            items.append(Item._from_xml(item_el))

        return ListBlock(items)


class Item:
    """Элемент списка."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def __iter__(self):
        return iter(self.blocks)

    def __str__(self):
        return "\n".join(str(p) for p in self.blocks)

    def __len__(self):
        return len(self.blocks)

    def __getitem__(self, index):
        return self.blocks[index]

    def _to_xml(self) -> ET.Element:
        el = ET.Element("item")

        for block in self.blocks:
            el.append(block._to_xml())

        return el

    @staticmethod
    def _from_xml(element: ET.Element) -> "Item":
        blocks = []

        for child in element:
            blocks.append(Block._from_xml(child))

        return Item(blocks)


class Table(Block):
    """Таблица."""

    def __init__(self, rows: List[Row]):
        self.rows: List[Row] = rows

    def __iter__(self):
        return iter(self.rows)

    def __str__(self):
        return "\n".join(str(p) for p in self.rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]

    def _to_xml(self):
        el = ET.Element("table")

        for row in self.rows:
            el.append(row._to_xml())

        return el

    @staticmethod
    def _from_xml(element):
        rows = []

        for row_el in element.findall("row"):
            rows.append(Row._from_xml(row_el))

        return Table(rows)


class Row:
    """Строка таблицы."""

    def __init__(self, cells: List[Cell]):
        self.cells: List[Cell] = cells

    def __iter__(self):
        return iter(self.cells)

    def __str__(self):
        return "\n".join(str(p) for p in self.cells)

    def __len__(self):
        return len(self.cells)

    def __getitem__(self, index):
        return self.cells[index]

    def _to_xml(self):
        el = ET.Element("row")

        for cell in self.cells:
            el.append(cell._to_xml())

        return el

    @staticmethod
    def _from_xml(element):
        cells = []

        for cell_el in element.findall("cell"):
            cells.append(Cell._from_xml(cell_el))

        return Row(cells)


class Cell:
    """Клетка таблицы."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def __iter__(self):
        return iter(self.blocks)

    def __str__(self):
        return "\n".join(str(p) for p in self.blocks)

    def __len__(self):
        return len(self.blocks)

    def __getitem__(self, index):
        return self.blocks[index]

    def _to_xml(self):
        el = ET.Element("cell")

        for block in self.blocks:
            el.append(block._to_xml())

        return el

    @staticmethod
    def _from_xml(element):
        blocks = []

        for child in element:
            blocks.append(Block._from_xml(child))

        return Cell(blocks)
