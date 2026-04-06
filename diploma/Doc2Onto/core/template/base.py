from abc import ABC, abstractmethod
from typing import Dict, List

from core.template.extraction_result import ExtractionResult
from core.template.field_validator import ValidationResult
from core.template.field import Field
from core.uddm import UDDM


class BaseTemplateCode(ABC):
    """Базовый класс для кода шаблона. Содержит методы, которые должны переопределить реальный код шаблона."""

    @abstractmethod
    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        """Определение класса документа. Должен возвращать True, если документ подходит под шаблон, и False иначе."""
        return False

    @abstractmethod
    def fields(self) -> List[Field]:
        """Определяет поля, которые нужно извлекать из документа. Должен возвращать список объектов Field."""
        raise NotImplementedError()

    # TODO: перенести привязку валидаторов полей напрямую в Field
    @abstractmethod
    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        """Проверяет корректность извлеченных данных."""
        pass

    @abstractmethod
    def build_triples(self, validation_result: ValidationResult) -> List[Dict]:
        """Построение RDF-триплетов из извлеченных данных."""
        pass
