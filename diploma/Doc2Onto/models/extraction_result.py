"""
Результат извлечения и нормализации полей документа.

Хранит ВСЮ историю значения поля от сырого текста до канонической формы:

* ``value_temp`` — что извлёк декларативный шаблон (selector + extractor).
* ``value_llm`` — что выдал LLM-этап Extractor-а (либо подтверждение
  template-значения, либо коррекция).
* ``value_normalized`` — каноническая строка после применения
  ``field.normalizer`` к raw-значению (LLM-приоритет, fallback на template).

Этот файл — единственное место, где для каждого поля хранятся все
промежуточные результаты пайплайна (Extractor + Normalizer). Стадия
GraphBuilder работает только с ``value_normalized``.
"""
import json
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional, TypedDict

from utils.general import parse_dict_field


class FieldExtractionData(TypedDict):
    # --- декларативное извлечение (Extractor: selector + extractor) ---
    extracted_temp: bool
    value_temp: Optional[str]
    error_temp: Optional[str]

    # --- LLM-этап Extractor (проверка/коррекция template-значения) ---
    # ``extracted_llm`` трёхзначный:
    #   None  — LLM экстракция ещё не запускалась для этого поля;
    #   True  — LLM экстракция/коррекция прошла успешно;
    #   False — LLM экстракция не удалась.
    extracted_llm: Optional[bool]
    value_llm: Optional[str]
    error_llm: Optional[str]

    # --- этап Normalizer (концепт + примитивы FieldNormalizer) ---
    # ``normalized`` строго трёхзначный:
    #   None  — стадия Normalizer ещё не запускалась для этого поля;
    #   True  — нормализация прошла, ``value_normalized`` содержит каноническую строку;
    #   False — нормализатор отверг raw-значение, ``error_normalized`` содержит причину.
    normalized: Optional[bool]
    value_normalized: Optional[str]
    error_normalized: Optional[str]


class FieldSituation(Enum):
    """Сводный статус поля, удобный для UI и логов."""

    OK = auto()                 # извлечено + нормализовано
    CORRECTED_LLM = auto()      # template-значение исправлено LLM-ом, нормализация прошла
    FOUND_BY_LLM = auto()       # template ничего не дал, LLM нашёл, нормализация прошла
    NOT_NORMALIZED = auto()     # значение есть (template или LLM), но Normalizer его отверг
    EXTRACTION_FAILED = auto()  # ни template, ни LLM значения не дали

    def short_msg(self) -> str:
        return {
            FieldSituation.OK: "extracted by template",
            FieldSituation.CORRECTED_LLM: "corrected by LLM",
            FieldSituation.FOUND_BY_LLM: "extracted by LLM",
            FieldSituation.NOT_NORMALIZED: "rejected by normalizer",
            FieldSituation.EXTRACTION_FAILED: "failed to extract",
        }[self]

    def warn_level(self) -> int:
        return {
            FieldSituation.OK: 0,
            FieldSituation.CORRECTED_LLM: 1,
            FieldSituation.FOUND_BY_LLM: 1,
            FieldSituation.NOT_NORMALIZED: 2,
            FieldSituation.EXTRACTION_FAILED: 2,
        }[self]


# Исторический алиас — оставлен для совместимости имени, но содержит новые члены.
FieldExtractionSituation = FieldSituation


class ExtractionResult:
    """Все собранные данные по полям документа: extraction + normalization."""

    def __init__(self):
        self.fields: Dict[str, FieldExtractionData] = {}

    def get_field(self, field_name: str) -> Optional[FieldExtractionData]:
        return self.fields.get(field_name)

    # --- extraction predicates ---

    def is_extracted_temp(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("extracted_temp", False))

    def is_extracted_llm(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("extracted_llm", False))

    def is_extracted_final(self, field_name: str) -> bool:
        data = self.fields.get(field_name)
        if data is None:
            return False
        if data.get("extracted_llm") is not None:
            return bool(data.get("extracted_llm"))
        return bool(data.get("extracted_temp"))

    def is_normalized(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("normalized"))

    def is_normalization_done(self, field_name: str) -> bool:
        """True, если стадия Normalizer уже отработала для этого поля
        (вне зависимости от результата)."""
        return self.fields.get(field_name, {}).get("normalized") is not None

    def is_all_normalized(self) -> bool:
        return all(self.is_normalized(name) for name in self.fields.keys())

    # --- value getters ---

    def get_value_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_temp")

    def get_value_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_llm")

    def get_value_raw(self, field_name: str) -> Optional[str]:
        """Извлечённое сырое значение (LLM в приоритете, fallback на template)."""
        return self.get_value_llm(field_name) or self.get_value_temp(field_name)

    def get_value_normalized(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_normalized")

    def get_value_final(self, field_name: str) -> Optional[str]:
        """Лучшее значение для UI: нормализованное, если есть; иначе сырое."""
        return self.get_value_normalized(field_name) or self.get_value_raw(field_name)

    # --- error getters ---

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    def get_error_normalized(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_normalized")

    # --- situation ---

    @staticmethod
    def get_situation_from_data(data: FieldExtractionData) -> FieldSituation:
        temp_ok = bool(data.get("extracted_temp", False))
        llm_ok = bool(data.get("extracted_llm", False))
        value_temp = data.get("value_temp")
        value_llm = data.get("value_llm")
        normalized = data.get("normalized")

        # Сначала отказ на этапе извлечения.
        if not temp_ok and not llm_ok:
            return FieldSituation.EXTRACTION_FAILED

        # Если нормализатор отработал и отверг — общий статус NOT_NORMALIZED,
        # независимо от того, кто (template или LLM) дал raw-значение.
        if normalized is False:
            return FieldSituation.NOT_NORMALIZED

        # Иначе классифицируем по источнику raw-значения.
        if temp_ok:
            if llm_ok and value_llm and value_llm != value_temp:
                return FieldSituation.CORRECTED_LLM
            return FieldSituation.OK
        return FieldSituation.FOUND_BY_LLM

    def get_situation(self, field_name: str) -> FieldSituation:
        data = self.fields.get(field_name)
        if not data:
            return FieldSituation.EXTRACTION_FAILED
        return self.get_situation_from_data(data)

    # --- mutators ---

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
        normalized: Optional[bool] = None,
        value_normalized: Optional[str] = None,
        error_normalized: Optional[str] = None,
    ):
        self.fields[field_name] = {
            "extracted_temp": extracted_temp,
            "value_temp": value_temp,
            "error_temp": error_temp,
            "extracted_llm": extracted_llm,
            "value_llm": value_llm,
            "error_llm": error_llm,
            "normalized": normalized,
            "value_normalized": value_normalized,
            "error_normalized": error_normalized,
        }

    def ensure_field(self, field_name: str):
        if field_name not in self.fields:
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

    def set_normalized(self, field_name: str, value: str):
        self.ensure_field(field_name)
        self.fields[field_name]["normalized"] = True
        self.fields[field_name]["value_normalized"] = value
        self.fields[field_name]["error_normalized"] = None

    def set_not_normalized(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["normalized"] = False
        self.fields[field_name]["value_normalized"] = None
        self.fields[field_name]["error_normalized"] = error

    # --- persistence ---

    @staticmethod
    def load(path: Path) -> "ExtractionResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid extraction result file: {path}")

        result = ExtractionResult()
        for field_name, item in data.items():
            if not isinstance(field_name, str) or not isinstance(item, dict):
                raise ValueError(f"Invalid record in extraction result file: {path}")
            result.set_result(
                field_name,
                extracted_temp=parse_dict_field(item, "extracted_temp", exp_type=bool, default=False),
                value_temp=parse_dict_field(item, "value_temp", exp_type=str, default=None),
                error_temp=parse_dict_field(item, "error_temp", exp_type=str, default=None),
                extracted_llm=parse_dict_field(item, "extracted_llm", exp_type=bool, default=None),
                value_llm=parse_dict_field(item, "value_llm", exp_type=str, default=None),
                error_llm=parse_dict_field(item, "error_llm", exp_type=str, default=None),
                normalized=parse_dict_field(item, "normalized", exp_type=bool, default=None),
                value_normalized=parse_dict_field(item, "value_normalized", exp_type=str, default=None),
                error_normalized=parse_dict_field(item, "error_normalized", exp_type=str, default=None),
            )
        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)
