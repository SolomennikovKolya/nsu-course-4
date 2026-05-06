import json
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional, TypedDict

from utils.general import parse_dict_field


class FieldExtractionData(TypedDict):
    extracted_temp: bool           # Статус декларативного (шаблонного) извлечения: удалось/не удалось получить значение
    value_temp: Optional[str]      # Значение, извлечённое по шаблону
    error_temp: Optional[str]      # Ошибка шаблонного извлечения
    extracted_llm: Optional[bool]  # Статус LLM-проверки/коррекции (None - если произошла непредвиденная ошибка LLM)
    value_llm: Optional[str]       # Итоговое значение по версии LLM (может совпадать с template или быть исправленным)
    error_llm: Optional[str]       # Ошибка или предупреждение LLM (для ok должно быть null)


class FieldExtractionSituation(Enum):
    OK = auto()
    CORRECTED = auto()
    WRONG = auto()
    FOUND = auto()
    FAILED = auto()

    def short_msg(self) -> str:
        msgs = {
            FieldExtractionSituation.OK: "extracted by template",
            FieldExtractionSituation.CORRECTED: "corrected by LLM",
            FieldExtractionSituation.WRONG: "incorrectly extracted",
            FieldExtractionSituation.FOUND: "extracted by LLM",
            FieldExtractionSituation.FAILED: "failed to extract",
        }
        return msgs[self]

    def warn_level(self) -> int:
        levels = {
            FieldExtractionSituation.OK: 0,
            FieldExtractionSituation.CORRECTED: 1,
            FieldExtractionSituation.WRONG: 2,
            FieldExtractionSituation.FOUND: 1,
            FieldExtractionSituation.FAILED: 2,
        }
        return levels[self]


class ExtractionResult:
    """
    Результат извлечения полей документа.
    Словарь вида {field_name: FieldExtractionData}
    """

    def __init__(self):
        self.fields: Dict[str, FieldExtractionData] = {}

    def get_field(self, field_name: str) -> Optional[FieldExtractionData]:
        return self.fields.get(field_name)

    def is_extracted_temp(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("extracted_temp", False))

    def is_extracted_llm(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("extracted_llm", False))

    def is_extracted_final(self, field_name: str) -> bool:
        data = self.fields.get(field_name)
        if data is None:
            return False

        # Если LLM уже дала результат, доверяем её итоговому статусу.
        # Иначе считаем успехом результат декларативного извлечения.
        if data.get("extracted_llm") is not None:
            return data.get("extracted_llm")
        return data.get("extracted_temp")

    def get_value_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_temp")

    def get_value_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_llm")

    def get_value_final(self, field_name: str) -> Optional[str]:
        return self.get_value_llm(field_name) or self.get_value_temp(field_name)

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    @staticmethod
    def get_situation_from_data(data: FieldExtractionData) -> FieldExtractionSituation:
        temp_ok = bool(data.get("extracted_temp", False))
        llm_ok = bool(data.get("extracted_llm", False))
        value_temp = data.get("value_temp")
        value_llm = data.get("value_llm")

        if temp_ok:
            if llm_ok:
                if value_llm is None or (value_llm == value_temp):
                    return FieldExtractionSituation.OK
                return FieldExtractionSituation.CORRECTED
            else:
                return FieldExtractionSituation.WRONG
        else:
            if llm_ok:
                return FieldExtractionSituation.FOUND
            return FieldExtractionSituation.FAILED

    def get_situation(self, field_name: str) -> FieldExtractionSituation:
        data = self.fields.get(field_name)
        if not data:
            return FieldExtractionSituation.FAILED
        return self.get_situation_from_data(data)

    def set_result(
            self,
            field_name: str,
            *,
            extracted_temp: bool = False,
            value_temp: Optional[str] = None,
            error_temp: Optional[str] = None,
            extracted_llm: Optional[bool] = None,
            value_llm: Optional[str] = None,
            error_llm: Optional[str] = None,
    ):
        self.fields[field_name] = {
            "extracted_temp": extracted_temp,
            "value_temp": value_temp,
            "error_temp": error_temp,
            "extracted_llm": extracted_llm,
            "value_llm": value_llm,
            "error_llm": error_llm,
        }

    def ensure_field(self, field_name: str):
        if field_name in self.fields:
            return

        self.set_result(field_name)

    def set_value_temp(self, field_name: str, value: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_temp"] = True
        self.fields[field_name]["value_temp"] = value
        self.fields[field_name]["error_temp"] = None

    def set_error_temp(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_temp"] = False
        self.fields[field_name]["value_temp"] = None
        self.fields[field_name]["error_temp"] = error

    def set_value_llm(self, field_name: str, value: str, warning: Optional[str] = None):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_llm"] = True
        self.fields[field_name]["value_llm"] = value
        self.fields[field_name]["error_llm"] = warning

    def set_error_llm(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_llm"] = False
        self.fields[field_name]["value_llm"] = None
        self.fields[field_name]["error_llm"] = error

    def set_unexpected_error_llm(self, field_name: str, fatal: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_llm"] = None
        self.fields[field_name]["value_llm"] = None
        self.fields[field_name]["error_llm"] = fatal

    @staticmethod
    def load(path: Path) -> "ExtractionResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid extraction result file: {path}")

        result = ExtractionResult()
        for field_name, item in data.items():
            if not isinstance(field_name, str):
                raise ValueError(f"Invalid field name in extraction result file: {path}")
            if not isinstance(item, dict):
                raise ValueError(f"Invalid value in extraction result file: {path}")

            result.set_result(
                field_name,
                extracted_temp=parse_dict_field(item, "extracted_temp", exp_type=bool, default=False),
                value_temp=parse_dict_field(item, "value_temp", exp_type=str, default=None),
                error_temp=parse_dict_field(item, "error_temp", exp_type=str, default=None),
                extracted_llm=parse_dict_field(item, "extracted_llm", exp_type=bool, default=None),
                value_llm=parse_dict_field(item, "value_llm", exp_type=str, default=None),
                error_llm=parse_dict_field(item, "error_llm", exp_type=str, default=None),
            )
        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)
