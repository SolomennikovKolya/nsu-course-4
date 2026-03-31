import re
from typing import List, Dict, Any


class FieldValidationError:
    def __init__(self, field_name: str, message: str, value=None):
        self.field_name = field_name
        self.message = message
        self.value = value


class ValidationResult:
    def __init__(self):
        self.validated: Dict[str, Any] = {}
        self.errors: List[FieldValidationError] = []

    def add_valid(self, field_name: str, value):
        self.validated[field_name] = value

    def add_error(self, field_name: str, message: str, value=None):
        error = FieldValidationError(field_name, message, value)
        self.errors.append(error)

    def is_valid(self) -> bool:
        return len(self.errors) == 0


class FieldValidator:
    def __init__(self):
        self.rules = []

    def validate(self, value, field_name: str, result: ValidationResult):
        for rule in self.rules:
            rule(value, field_name, result)

    def required(self):
        def rule(value, field_name, result: ValidationResult):
            if value is None or value == "":
                result.add_error(field_name, "Обязательное поле отсутствует", value)

        self.rules.append(rule)
        return self

    def regex(self, pattern: str):
        def rule(value, field_name, result: ValidationResult):
            if value is None:
                return

            if not re.match(pattern, str(value)):
                result.add_error(field_name, f"Не соответствует шаблону {pattern}", value)

        self.rules.append(rule)
        return self

    def in_range(self, min_val, max_val):
        def rule(value, field_name, result: ValidationResult):
            try:
                v = float(value)
                if not (min_val <= v <= max_val):
                    result.add_error(field_name, f"Значение вне диапазона [{min_val}, {max_val}]", value)
            except:
                result.add_error(field_name, "Некорректное числовое значение", value)

        self.rules.append(rule)
        return self

    def custom(self, func):
        self.rules.append(func)
        return self


def validate() -> FieldValidator:
    return FieldValidator()
