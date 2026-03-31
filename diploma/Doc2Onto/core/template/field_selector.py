from typing import List, Callable

from core.uddm import UDDM


class FieldSelector:
    def __init__(self):
        self.operations: List[Callable[[UDDM, List[str]], List[str]]] = []

    def select(self, uddm: UDDM) -> List[str]:
        result: List[str] = []

        for op in self.operations:
            result = op(uddm, result)

        return result

    def paragraph_contains(self, text: str):
        def op(uddm: UDDM, _: List[str]) -> List[str]:
            return [
                str(p) for p in uddm.iter_paragraphs()
                if text.lower() in str(p).lower()
            ]

        self.operations.append(op)
        return self

    def paragraph_after(self, text: str):
        def op(uddm: UDDM, _: List[str]) -> List[str]:
            paragraphs = uddm.get_all_texts_from_paragraphs()

            for i, p in enumerate(paragraphs):
                if text.lower() in p.lower() and i + 1 < len(paragraphs):
                    return [paragraphs[i + 1]]

            return []

        self.operations.append(op)
        return self

    def paragraph_index(self, index: int):
        def op(uddm: UDDM, _: List[str]) -> List[str]:
            paragraphs = uddm.get_all_texts_from_paragraphs()
            if 0 <= index < len(paragraphs):
                return [paragraphs[index]]
            return []

        self.operations.append(op)
        return self

    def table_cell_contains(self, text: str):
        def op(uddm: UDDM, _: List[str]) -> List[str]:
            result = []

            for table in uddm.get_all_tables():
                for row in table:
                    for cell in row:
                        if text.lower() in str(cell).lower():
                            result.append(cell)

            return result

        self.operations.append(op)
        return self

    def right_cell(self):
        def op(uddm: UDDM, prev: List[str]) -> List[str]:
            if not prev:
                return []

            result = []

            for table in uddm.get_all_tables():
                for row in table:
                    for i, cell in enumerate(row):
                        if cell in prev and i + 1 < len(row):
                            result.append(row[i + 1])

            return result

        self.operations.append(op)
        return self


def select() -> FieldSelector:
    return FieldSelector()
