from abc import ABC, abstractmethod
from typing import Dict, List

from core.template.field_validator import ValidationResult
from core.template.field import Field
from core.uddm import UDDM


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


class BaseTemplateCode(ABC):
    """Базовый класс для шаблонов. Содержит методы, которые должны переопределить реальные шаблоны."""

    @abstractmethod
    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        """Определение класса документа. Должен возвращать True, если документ подходит под шаблон, и False иначе."""
        return False

    @abstractmethod
    def fields(self) -> List[Field]:
        """Определяет поля, которые нужно извлекать из документа. Должен возвращать список объектов Field."""
        raise NotImplementedError()

    @abstractmethod
    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        """Проверяет корректность извлеченных данных."""
        pass

    @abstractmethod
    def build_triples(self, validation_result: ValidationResult) -> List[Dict]:
        """Построение RDF-триплетов из извлеченных данных."""
        pass
