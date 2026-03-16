from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List


class UDDM:
    """
    Объектная модель документа в формате UDDM.

    Пример использования:
    Создание:
    doc = UDDM([
        Text([
            P("Paragraph 1"),
            P("Paragraph 2")
        ])
    ])

    Сохранение:
    doc.save("file.uddm.xml")

    Загрузка:
    doc = UDDM.load("file.uddm.xml")
    """

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def to_xml(self) -> ET.Element:
        root = ET.Element("document")

        for block in self.blocks:
            root.append(block.to_xml())

        return root

    def save(self, path: Path):
        tree = ET.ElementTree(self.to_xml())
        tree.write(path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def load(path) -> "UDDM":
        tree = ET.parse(path)
        root = tree.getroot()

        blocks = []

        for child in root:
            blocks.append(Block.from_xml(child))

        return UDDM(blocks)


class Block:
    """Базовый блок UDDM."""

    def to_xml(self) -> ET.Element:
        raise NotImplementedError

    @staticmethod
    def from_xml(element: ET.Element) -> "Block":
        tag = element.tag

        if tag == "text":
            return Text.from_xml(element)

        if tag == "list":
            return ListBlock.from_xml(element)

        if tag == "table":
            return Table.from_xml(element)

        raise ValueError(f"Unknown block type: {tag}")


class Text(Block):
    """Текстовый блок, состоящий из параграфов."""

    def __init__(self, paragraphs: List[P]):
        self.paragraphs: List[P] = paragraphs

    def to_xml(self) -> ET.Element:
        el = ET.Element("text")

        for p in self.paragraphs:
            el.append(p.to_xml())

        return el

    @staticmethod
    def from_xml(element: ET.Element) -> "Text":
        paragraphs = []

        for p in element.findall("p"):
            paragraphs.append(P.from_xml(p))

        return Text(paragraphs)


class P:
    """Параграф - атомарный элемент текста."""

    def __init__(self, text: str):
        self.text: str = text

    def to_xml(self) -> ET.Element:
        el = ET.Element("p")
        el.text = self.text
        return el

    @staticmethod
    def from_xml(element: ET.Element) -> "P":
        return P(element.text or "")


class ListBlock(Block):
    """Список."""

    def __init__(self, items: List[Item]):
        self.items: List[Item] = items

    def to_xml(self) -> ET.Element:
        el = ET.Element("list")

        for item in self.items:
            el.append(item.to_xml())

        return el

    @staticmethod
    def from_xml(element: ET.Element) -> "ListBlock":
        items = []

        for item_el in element.findall("item"):
            items.append(Item.from_xml(item_el))

        return ListBlock(items)


class Item:
    """Элемент списка."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def to_xml(self) -> ET.Element:
        el = ET.Element("item")

        for block in self.blocks:
            el.append(block.to_xml())

        return el

    @staticmethod
    def from_xml(element: ET.Element) -> "Item":
        blocks = []

        for child in element:
            blocks.append(Block.from_xml(child))

        return Item(blocks)


class Table(Block):
    """Таблица."""

    def __init__(self, rows: List[Row]):
        self.rows: List[Row] = rows

    def to_xml(self):

        el = ET.Element("table")

        for row in self.rows:
            el.append(row.to_xml())

        return el

    @staticmethod
    def from_xml(element):

        rows = []

        for row_el in element.findall("row"):
            rows.append(Row.from_xml(row_el))

        return Table(rows)


class Row:
    """Строка таблицы."""

    def __init__(self, cells: List[Cell]):
        self.cells: List[Cell] = cells

    def to_xml(self):
        el = ET.Element("row")

        for cell in self.cells:
            el.append(cell.to_xml())

        return el

    @staticmethod
    def from_xml(element):
        cells = []

        for cell_el in element.findall("cell"):
            cells.append(Cell.from_xml(cell_el))

        return Row(cells)


class Cell:
    """Клетка таблицы."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def to_xml(self):
        el = ET.Element("cell")

        for block in self.blocks:
            el.append(block.to_xml())

        return el

    @staticmethod
    def from_xml(element):
        blocks = []

        for child in element:
            blocks.append(Block.from_xml(child))

        return Cell(blocks)
