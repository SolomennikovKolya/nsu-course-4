from typing import Dict, Optional, TypedDict
from logging import WARNING, INFO
from pathlib import Path
import json

from core.document import Document
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult
from core.template.template import Template


class FieldValidationData(TypedDict):
    valid: bool
    value: Optional[str]
    message: Optional[str]


class ValidationResult:
    """Результат валидации набора полей"""

    def __init__(self):
        self.fields: Dict[str, FieldValidationData] = {}

    def set_result(self, field_name: str, valid: bool, value: Optional[str], message: Optional[str]):
        self.fields[field_name] = {
            "valid": valid,
            "value": value,
            "message": message,
        }

    def add_error(self, field_name: str, message: str, value: Optional[str] = None):
        self.set_result(field_name, False, value, message)

    def add_valid(self, field_name: str, value: Optional[str]):
        self.set_result(field_name, True, value, None)

    def is_valid(self) -> bool:
        return all(field_result["valid"] for field_result in self.fields.values())

    @staticmethod
    def load(path: Path) -> "ValidationResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid validation result file: {path}")

        result = ValidationResult()
        for field_name, field_result in data.items():
            if not isinstance(field_result, dict):
                continue
            valid = bool(field_result.get("valid", False))
            raw_value = field_result.get("value")
            raw_message = field_result.get("message")
            value = raw_value if isinstance(raw_value, str) else None
            message = raw_message if isinstance(raw_message, str) else None
            result.set_result(str(field_name), valid, value, message)

        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)


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

        ALIGN_WIDTH = 30
        result = ValidationResult()
        for field in template.fields:
            try:
                field_label = f"{field.name}:".ljust(ALIGN_WIDTH)
                value = extraction_result.get(field.name)
                if value is None:
                    result.add_error(field.name, "Значение поля отсутствует")
                    self.log(WARNING, f"{field_label} value is missing")
                    continue

                message = field.validator._validate(value)
                if message:
                    result.add_error(field.name, message, value)
                    self.log(WARNING, f"{field_label} error validating field: {message}")
                    continue

                result.add_valid(field.name, value)
                self.log(INFO, f"{field_label} valid")

            except Exception:
                result.add_error(field.name, "Ошибка валидации")
                self.log(WARNING, f"{field_label} error validating field", exc_info=True)

        return result
