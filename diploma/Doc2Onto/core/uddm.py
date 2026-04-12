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
        ```python
        doc = UDDM([
            Text([
                P("Paragraph 1"),
                P("Paragraph 2")
            ])
        ])
        ```
        """
        self.root = Root(blocks)

    # ----- итераторы -----

    def iter_blocks(self) -> Iterator[Block]:
        """Итератор для обхода всех блоков."""
        for block in self.root.blocks:
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

    def iter_texts(self) -> Iterator[Text]:
        """Итератор для обхода всех текстовых блоков."""
        for block in self.iter_blocks():
            if isinstance(block, Text):
                yield block

    def iter_paragraphs(self) -> Iterator[P]:
        """Итератор для обхода всех абзацев."""
        for text in self.iter_texts():
            for p in text.paragraphs:
                yield p

    def iter_lists(self) -> Iterator[ListBlock]:
        """Итератор для обхода всех списков."""
        for block in self.iter_blocks():
            if isinstance(block, ListBlock):
                yield block

    def iter_tables(self) -> Iterator[Table]:
        """Итератор для обхода всех таблиц."""
        for block in self.iter_blocks():
            if isinstance(block, Table):
                yield block

    # ----- геттеры -----

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

    @staticmethod
    def load(path: Path) -> "UDDM":
        """Десериализация из xml-файла."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            blocks = [Block._from_xml(b) for b in root]
            return UDDM(blocks)

        except FileNotFoundError as e:
            raise FileNotFoundError(f"XML файл не найден: {path}") from e

        except ET.ParseError as e:
            raise ET.ParseError(f"Ошибка парсинга XML файла {path}: {e}") from e

        except ValueError as e:
            raise ValueError(f"Ошибка при десериализации блока: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Неожиданная ошибка при загрузке UDDM из {path}: {e}") from e

    def save(self, path: Path):
        """Сериализация в xml-файл."""
        tree = ET.ElementTree(self.root._to_xml())
        tree.write(path, encoding="utf-8", xml_declaration=True)


class UDDMElement(ABC):
    """Базовый тип для узлов дерева UDDM."""

    @abstractmethod
    def __str__(self) -> str:
        """Строковое представление элемента."""
        raise NotImplementedError

    @abstractmethod
    def __iter__(self) -> Iterator["UDDMElement"]:
        """Итератор для обхода всех дочерних элементов."""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """Количество дочерних элементов."""
        raise NotImplementedError

    @abstractmethod
    def __getitem__(self, index: int) -> "UDDMElement":
        """Получение элемента по индексу."""
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _from_xml(element: ET.Element) -> "UDDMElement":
        """Десериализация из xml-элемента."""
        raise NotImplementedError

    @abstractmethod
    def _to_xml(self) -> ET.Element:
        """Сериализация в xml-элемент."""
        raise NotImplementedError


class Root(UDDMElement):
    """Корень документа."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def __str__(self) -> str:
        return "\n".join(str(b) for b in self.blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __getitem__(self, index: int) -> Block:
        return self.blocks[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Root":
        return Root([Block._from_xml(b) for b in element])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("root")
        el.extend(b._to_xml() for b in self.blocks)
        return el


class Block(ABC):
    """Абстрактный базовый блок UDDM."""

    @staticmethod
    def _from_xml(element: ET.Element) -> "Block":
        tag = element.tag

        if tag == "text":
            return Text._from_xml(element)

        if tag == "list":
            return ListBlock._from_xml(element)

        if tag == "table":
            return Table._from_xml(element)

        raise ValueError(f"Неизвестный тип блока: {tag}")

    @abstractmethod
    def _to_xml(self) -> ET.Element:
        raise NotImplementedError


class Text(Block, UDDMElement):
    """Текстовый блок, состоящий из параграфов."""

    def __init__(self, paragraphs: List[P]):
        self.paragraphs: List[P] = paragraphs

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.paragraphs)

    def __iter__(self) -> Iterator[P]:
        return iter(self.paragraphs)

    def __len__(self) -> int:
        return len(self.paragraphs)

    def __getitem__(self, index: int) -> P:
        return self.paragraphs[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Text":
        return Text([P._from_xml(p) for p in element.findall("p")])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("text")
        el.extend(p._to_xml() for p in self.paragraphs)
        return el


class P(UDDMElement):
    """Параграф - атомарный элемент текста."""

    def __init__(self, text: str):
        self.text: str = text

    def __str__(self) -> str:
        return self.text

    def __iter__(self) -> Iterator[str]:
        return iter(self.text)

    def __len__(self) -> int:
        return len(self.text)

    def __getitem__(self, index: int) -> str:
        return self.text[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "P":
        return P(element.text or "")

    def _to_xml(self) -> ET.Element:
        el = ET.Element("p")
        el.text = self.text
        return el


class ListBlock(Block, UDDMElement):
    """Список."""

    def __init__(self, items: List[Item]):
        self.items: List[Item] = items

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.items)

    def __iter__(self) -> Iterator[Item]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Item:
        return self.items[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "ListBlock":
        return ListBlock([Item._from_xml(i) for i in element.findall("item")])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("list")
        el.extend(i._to_xml() for i in self.items)
        return el


class Item(UDDMElement):
    """Элемент списка."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __getitem__(self, index: int) -> Block:
        return self.blocks[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Item":
        return Item([Block._from_xml(b) for b in element])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("item")
        el.extend(b._to_xml() for b in self.blocks)
        return el


class Table(Block, UDDMElement):
    """Таблица."""

    def __init__(self, rows: List[Row]):
        self.rows: List[Row] = rows

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.rows)

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> Row:
        return self.rows[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Table":
        return Table([Row._from_xml(r) for r in element.findall("row")])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("table")
        el.extend(r._to_xml() for r in self.rows)
        return el


class Row(UDDMElement):
    """Строка таблицы."""

    def __init__(self, cells: List[Cell]):
        self.cells: List[Cell] = cells

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.cells)

    def __iter__(self) -> Iterator[Cell]:
        return iter(self.cells)

    def __len__(self) -> int:
        return len(self.cells)

    def __getitem__(self, index: int) -> Cell:
        return self.cells[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Row":
        return Row([Cell._from_xml(c) for c in element.findall("cell")])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("row")
        el.extend(c._to_xml() for c in self.cells)
        return el


class Cell(UDDMElement):
    """Клетка таблицы."""

    def __init__(self, blocks: List[Block]):
        self.blocks: List[Block] = blocks

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __getitem__(self, index: int) -> Block:
        return self.blocks[index]

    @staticmethod
    def _from_xml(element: ET.Element) -> "Cell":
        return Cell([Block._from_xml(b) for b in element])

    def _to_xml(self) -> ET.Element:
        el = ET.Element("cell")
        el.extend(b._to_xml() for b in self.blocks)
        return el
