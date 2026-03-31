from __future__ import annotations

from enum import StrEnum
from typing import List

from core.uddm import UDDM
from core.template.field_selector import FieldSelector
from core.template.field_extractor import FieldExtractor
from core.template.field_validator import FieldValidator


class Field:
    """Содержит описание поля документа и информацию о том, как его извлекать."""

    class Type(StrEnum):
        INDIVIDUAL = "individual"
        LITERAL = "literal"

    def __init__(self, name: str, description: str,
                 selector: FieldSelector, extractor: FieldExtractor, validator: FieldValidator, field_type: Type):
        self.name: str = name
        self.description: str = description         # Для LLM fallback и UI
        self.selector: FieldSelector = selector     # Где искать
        self.extractor: FieldExtractor = extractor  # Как извлекать
        self.validator: FieldValidator = validator  # Как валидировать
        self.field_type: Field.Type = field_type    # Чем является

    def extract(self, uddm: UDDM):
        """Извлекает значение поля из UDDM, используя селектор и экстрактор."""
        try:
            texts: List[str] = self.selector.select(uddm)
            if not texts:
                return None

            combined = "\n".join(texts)
            value = self.extractor.extract(combined)
            return value

        except Exception:
            return None
