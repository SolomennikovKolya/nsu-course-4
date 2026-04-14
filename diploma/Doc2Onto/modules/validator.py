from typing import Dict, List, Any, Optional
from logging import WARNING
from pathlib import Path
import json

from core.document import Document
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult
from core.template.template import Template


class FieldValidationError:
    def __init__(self, field_name: str, value: Optional[str], message: str):
        self.field_name = field_name
        self.value = value
        self.message = message


class ValidationResult:
    """Результат валидации набора полей"""

    def __init__(self):
        self.validated: Dict[str, str] = {}
        self.errors: List[FieldValidationError] = []

    def add_valid(self, field_name: str, value: str) -> None:
        self.validated[field_name] = value

    def add_error(self, field_name: str, value: Optional[str], message: str) -> None:
        self.errors.append(FieldValidationError(field_name, value, message))

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @staticmethod
    def load(path: Path) -> "ValidationResult":
        with path.open("r", encoding="utf-8") as f:
            validated = json.load(f)
            errors = json.load(f)
            return ValidationResult(validated, errors)

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.validated, f, indent=2, ensure_ascii=False)
            json.dump(self.errors, f, indent=2, ensure_ascii=False)


class Validator(BaseModule):
    """Валидация извлечённых RDF-термов."""

    def __init__(self):
        super().__init__()

    def execute(self, document: Document) -> ModuleResult:
        try:
            if not document.doc_class or not document.template:
                self.log(WARNING, f"No template found")
                return ModuleResult.FAILED

            if not document.template.code:
                self.log(WARNING, f"Template {document.template.name} has no code")
                return ModuleResult.FAILED

            extraction_result = ExtractionResult.load(document.extraction_result_file_path())
            validation_result = self._validate(document.template, extraction_result)
            validation_result.save(document.validation_result_file_path())
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _validate(self, template: Template, extraction_result: ExtractionResult) -> ValidationResult:
        if not template.fields:
            template.fields = template.code.fields()

        result = ValidationResult()
        for field in template.fields:
            try:
                value = extraction_result.get(field.name)
                if value is None:
                    result.add_error(field.name, None, "Значение поля отсутствует")
                    continue

                message = field.validator._validate(value)
                if message:
                    result.add_error(field.name, value, message)
                    continue

                result.add_valid(field.name, value)

            except Exception:
                self.log(WARNING, f"Error validating field {field.name}", exc_info=True)

        return result
