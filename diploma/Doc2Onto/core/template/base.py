from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, TYPE_CHECKING

from core.template.field_validator import ValidationResult
from core.template.field import Field

# Импорт только для проверки типов, чтобы избежать циклической зависимости
if TYPE_CHECKING:
    from core.document import Document


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
    def classify(self, document: Document) -> bool:
        """Определение класса документа. Должен возвращать True, если документ подходит под шаблон, и False иначе."""
        return False

    # TODO: перенести в модуль экстрактора
    # def _extract(self, uddm: UDDM) -> ExtractionResult:
    #     result = ExtractionResult()

    #     for field in self.fields():
    #         value = field.extract(uddm)
    #         result.add(field, value)

    #     return result

    @abstractmethod
    def fields(self) -> List[Field]:
        """Определяет поля, которые нужно извлекать из документа. Должен возвращать список объектов Field."""
        raise NotImplementedError()

    # TODO: перенести в модуль валидатора
    # def _run_validation(self, extraction_result: ExtractionResult) -> ValidationResult:
    #     result = ValidationResult()

    #     for field in self.fields():
    #         value = extraction_result.values.get(field.name, {}).get("value")

    #         if field.validator:
    #             field.validator.validate(value, field.name, result)

    #         if field.name not in result.errors:
    #             result.add_valid(field.name, value)

    #     return result

    @abstractmethod
    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        """Проверяет корректность извлеченных данных."""
        pass

    @abstractmethod
    def build_triples(self, validation_result: ValidationResult) -> List[Dict]:
        """Построение RDF-триплетов из извлеченных данных."""
        pass
