from rdflib import Literal, URIRef
from typing import Optional, Dict
import re


def sanitize(value: str) -> str:
    if not value:
        return ""

    # Оставляем только буквы (латиница + кириллица) и цифры
    # Всё остальное → пробел
    value = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", value)

    # Разбиваем на слова
    words = value.strip().split()
    if not words:
        return ""

    # CamelCase (PascalCase)
    words = [w.capitalize() for w in words]
    return "".join(words)


def sanitize_camel(value: str) -> str:
    s = sanitize(value)
    return s[:1].lower() + s[1:] if s else s


class FieldsAccessor:
    """Аксессор к извлечённым значениям полей."""

    def __init__(self, values: Dict[str, str]):
        self._values = values

    def value(self, name: str) -> Optional[str]:
        return self._values.get(name)

    def literal(self, name: str, value_type: type = str) -> Literal:
        val = self.value(name)
        if val is not None and value_type is not str:
            try:
                val = value_type(val)
            except (ValueError, TypeError):
                pass
        return Literal(val)

    def uri(self, name: str, prefix: str) -> URIRef:
        val = self.value(name)
        # if val is None:
        #     raise ValueError(f"Cannot build URI for field {name}: value is None")
        return URIRef(prefix + sanitize_camel(val))
