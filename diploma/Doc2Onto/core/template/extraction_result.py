from typing import Dict

from core.template.field import Field


class ExtractionResult:
    """Результат извлечения полей документа по шаблону. Содержит значения полей и их описание."""

    def __init__(self):
        self.values: Dict[str, Dict] = {}

    def add(self, field: Field, value):
        self.values[field.name] = {
            "value": value,
            "description": field.description,
            "field_type": field.field_type
        }
