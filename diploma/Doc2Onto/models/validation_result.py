import json
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional, TypedDict

from utils.general import parse_dict_field


class FieldValidationData(TypedDict):
    valid_temp: bool           # Статус шаблонной (жёсткой) валидации
    error_temp: Optional[str]  # Ошибка шаблонной валидации
    valid_llm: Optional[bool]  # Статус LLM-валидации/коррекции (None - непредвиденная ошибка)
    error_llm: Optional[str]   # Ошибка LLM (что не так с значением)


class FieldValidationSituation(Enum):
    VALID = auto()
    NONSENSE = auto()
    INVALID = auto()

    def short_msg(self) -> str:
        msgs = {
            FieldValidationSituation.VALID: "validated",
            FieldValidationSituation.NONSENSE: "rejected by LLM",
            FieldValidationSituation.INVALID: "rejected by template",
        }
        return msgs[self]

    def warn_level(self) -> int:
        levels = {
            FieldValidationSituation.VALID: 0,
            FieldValidationSituation.NONSENSE: 2,
            FieldValidationSituation.INVALID: 2,
        }
        return levels[self]


class ValidationResult:
    """Результат валидации набора полей."""

    def __init__(self):
        self.fields: Dict[str, FieldValidationData] = {}

    def get_field(self, field_name: str) -> Optional[FieldValidationData]:
        return self.fields.get(field_name)

    def is_valid_temp(self, field_name: str) -> bool:
        return self.fields.get(field_name, {}).get("valid_temp", False)

    def is_valid_llm(self, field_name: str) -> Optional[bool]:
        return self.fields.get(field_name, {}).get("valid_llm")

    def is_valid_final(self, field_name: str) -> bool:
        data = self.fields.get(field_name)
        if data is None:
            return False

        # Результат считается валидным, если и шаблон, и LLM считают его валидным
        # (но LLM может быть None, если произошла ошибка)
        if data.get("valid_llm") is not None:
            return data.get("valid_temp") and data.get("valid_llm")
        return data.get("valid_temp")

    def is_all_valid(self) -> bool:
        return all(self.is_valid_final(field_name) for field_name in self.fields.keys())

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    @staticmethod
    def get_situation_from_data(data: FieldValidationData) -> FieldValidationSituation:
        if data.get("valid_temp"):
            if data.get("valid_llm"):
                return FieldValidationSituation.VALID
            else:
                return FieldValidationSituation.NONSENSE
        else:
            return FieldValidationSituation.INVALID

    def get_situation(self, field_name: str) -> FieldValidationSituation:
        data = self.fields.get(field_name)
        if not data:
            return FieldValidationSituation.INVALID
        return self.get_situation_from_data(data)

    def set_result(
            self,
            field_name: str,
            *,
            valid_temp: bool = False,
            error_temp: Optional[str] = None,
            valid_llm: Optional[bool] = None,
            error_llm: Optional[str] = None,
    ):
        self.fields[field_name] = {
            "valid_temp": valid_temp,
            "error_temp": error_temp,
            "valid_llm": valid_llm,
            "error_llm": error_llm,
        }

    def ensure_field(self, field_name: str):
        if field_name in self.fields:
            return

        self.set_result(field_name)

    def set_valid_temp(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_temp"] = True
        self.fields[field_name]["error_temp"] = None

    def set_invalid_temp(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_temp"] = False
        self.fields[field_name]["error_temp"] = error

    def set_valid_llm(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = True
        self.fields[field_name]["error_llm"] = None

    def set_invalid_llm(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = False
        self.fields[field_name]["error_llm"] = error

    def set_unexpected_error_llm(self, field_name: str, fatal: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = None
        self.fields[field_name]["error_llm"] = fatal

    @staticmethod
    def load(path: Path) -> "ValidationResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid validation result file: {path}")

        result = ValidationResult()
        for field_name, field_data in data.items():
            if not isinstance(field_name, str):
                raise ValueError(f"Invalid field name in validation result file: {path}")
            if not isinstance(field_data, dict):
                raise ValueError(f"Invalid value in validation result file: {path}")

            result.set_result(
                field_name,
                valid_temp=parse_dict_field(field_data, "valid_temp", exp_type=bool, default=False),
                error_temp=parse_dict_field(field_data, "error_temp", exp_type=str, default=None),
                valid_llm=parse_dict_field(field_data, "valid_llm", exp_type=bool, default=None),
                error_llm=parse_dict_field(field_data, "error_llm", exp_type=str, default=None),
            )
        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)
