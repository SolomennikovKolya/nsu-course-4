import re
from typing import Callable, Optional, List, Union


class FieldExtractor:
    def __init__(self):
        self.operations: List[Callable[[str], Union[Optional[str], list]]] = []
        self.postprocess: List[Callable[[str], Optional[str]]] = []
        self.mode = "first"  # или "all"

    def extract(self, text: str):
        value: Union[str, list, None] = text

        for op in self.operations:
            if value is None:
                return None
            if isinstance(value, list):
                return value
            value = op(value)

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

        return value

    def regex(self, pattern: str):
        def op(text: str):
            matches = re.findall(pattern, text)
            if not matches:
                return None

            return matches if self.mode == "all" else matches[0]

        self.operations.append(op)
        return self

    def after(self, marker: str):
        def op(text: str):
            idx = text.lower().find(marker.lower())
            if idx == -1:
                return None
            return text[idx + len(marker):]

        self.operations.append(op)
        return self

    def before(self, marker: str):
        def op(text: str):
            idx = text.lower().find(marker.lower())
            if idx == -1:
                return text
            return text[:idx]

        self.operations.append(op)
        return self

    def custom(self, func: Callable[[str], Optional[str]]):
        self.operations.append(func)
        return self

    def first(self):
        self.mode = "first"
        return self

    def all(self):
        self.mode = "all"
        return self


def extract() -> FieldExtractor:
    return FieldExtractor()
