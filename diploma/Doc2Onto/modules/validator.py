from typing import Dict, List, Any, Optional
from logging import WARNING, INFO
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

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "message": self.message,
        }

    @staticmethod
    def from_dict(data: Dict[str, Optional[str]]) -> "FieldValidationError":
        return FieldValidationError(
            field_name=str(data.get("field_name", "")),
            value=data.get("value"),
            message=str(data.get("message", "")),
        )


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
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid validation result file: {path}")

        result = ValidationResult()
        validated = data.get("validated", {})
        errors = data.get("errors", [])

        if isinstance(validated, dict):
            result.validated = {
                str(field_name): value
                for field_name, value in validated.items()
                if isinstance(value, str)
            }

        if isinstance(errors, list):
            result.errors = [
                FieldValidationError.from_dict(item)
                for item in errors
                if isinstance(item, dict)
            ]

        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            data = {
                "validated": self.validated,
                "errors": [error.to_dict() for error in self.errors],
            }
            json.dump(data, f, indent=2, ensure_ascii=False)


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
                    self.log(WARNING, f"Value for field {field.name} is missing")
                    continue

                message = field.validator._validate(value)
                if message:
                    result.add_error(field.name, value, message)
                    self.log(WARNING, f"Error validating field {field.name}: {message}")
                    continue

                result.add_valid(field.name, value)
                self.log(INFO, f"Field {field.name} validated successfully")

            except Exception:
                result.add_error(field.name, None, "Ошибка валидации")
                self.log(WARNING, f"Error validating field {field.name}", exc_info=True)

        return result
