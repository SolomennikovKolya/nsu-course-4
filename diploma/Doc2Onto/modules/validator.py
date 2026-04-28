import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, List
from pathlib import Path
from enum import Enum, auto

from app.agents import ask_gpt, read_prompt
from app.utils import parse_dict_field
from app.settings import VALIDATE_FIELDS_SYS_PROMPT_PATH, VALIDATE_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from models.document import DocumentContext
from core.template.field import Field
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult


class FieldValidationData(TypedDict):
    valid_temp: bool              # Статус шаблонной (жёсткой) валидации
    error_temp: Optional[str]     # Ошибка шаблонной валидации
    valid_llm: Optional[bool]     # Статус LLM-валидации/коррекции (None - непредвиденная ошибка)
    value_llm: Optional[str]      # Значение после LLM-проверки/коррекции
    error_llm: Optional[str]      # Ошибка или предупреждение LLM
    valid_manual: Optional[bool]  # Ручной флаг валидности (None - пользователь не задавал)
    value_manual: Optional[str]   # Ручное значение (None - пользователь не задавал)


class FieldValidationSituation(Enum):
    VALID_TEMPLATE = auto()
    CORRECTED_LLM = auto()
    INVALID_AFTER_LLM = auto()
    VALID_MANUAL = auto()
    INVALID_MANUAL = auto()
    FAILED = auto()

    def full_msg(self) -> str:
        msgs = {
            FieldValidationSituation.VALID_TEMPLATE: "valid by template",
            FieldValidationSituation.CORRECTED_LLM: "validated/corrected by LLM",
            FieldValidationSituation.INVALID_AFTER_LLM: "invalid after LLM",
            FieldValidationSituation.VALID_MANUAL: "validated manually",
            FieldValidationSituation.INVALID_MANUAL: "invalid manually",
            FieldValidationSituation.FAILED: "validation failed",
        }
        return msgs[self]


class ValidationResult:
    """Результат валидации набора полей"""

    def __init__(self):
        self.fields: Dict[str, FieldValidationData] = {}

    def get_field(self, field_name: str) -> Optional[FieldValidationData]:
        return self.fields.get(field_name)

    def is_valid_temp(self, field_name: str) -> bool:
        return self.fields.get(field_name, {}).get("valid_temp", False)

    def is_valid_llm(self, field_name: str) -> Optional[bool]:
        return self.fields.get(field_name, {}).get("valid_llm")

    def is_valid_manual(self, field_name: str) -> Optional[bool]:
        return self.fields.get(field_name, {}).get("valid_manual")

    def is_valid_final(self, field_name: str) -> bool:
        data = self.fields.get(field_name)
        if data is None:
            return False
        if data.get("valid_manual") is not None:
            return bool(data.get("valid_manual"))
        if data.get("valid_llm") is not None:
            return bool(data.get("valid_llm"))
        return bool(data.get("valid_temp"))

    def is_all_valid(self) -> bool:
        return all(self.is_valid_final(field_name) for field_name in self.fields.keys())

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    def get_value_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_llm")

    def get_value_manual(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_manual")

    def get_value_final(self, field_name: str, extracted_value: Optional[str]) -> Optional[str]:
        return self.get_value_manual(field_name) or self.get_value_llm(field_name) or extracted_value

    @staticmethod
    def get_situation_from_data(data: FieldValidationData) -> FieldValidationSituation:
        if data.get("valid_manual") is True:
            return FieldValidationSituation.VALID_MANUAL
        if data.get("valid_manual") is False:
            return FieldValidationSituation.INVALID_MANUAL
        if data.get("valid_llm") is True:
            if data.get("value_llm") is not None:
                return FieldValidationSituation.CORRECTED_LLM
            return FieldValidationSituation.VALID_TEMPLATE
        if data.get("valid_llm") is False:
            return FieldValidationSituation.INVALID_AFTER_LLM
        if data.get("valid_temp"):
            return FieldValidationSituation.VALID_TEMPLATE
        return FieldValidationSituation.FAILED

    def get_situation(self, field_name: str) -> FieldValidationSituation:
        data = self.fields.get(field_name)
        if not data:
            return FieldValidationSituation.FAILED
        return self.get_situation_from_data(data)

    def set_result(
            self,
            field_name: str,
            *,
            valid_temp: bool = False,
            error_temp: Optional[str] = None,
            valid_llm: Optional[bool] = None,
            value_llm: Optional[str] = None,
            error_llm: Optional[str] = None,
            valid_manual: Optional[bool] = None,
            value_manual: Optional[str] = None
    ):
        self.fields[field_name] = {
            "valid_temp": valid_temp,
            "error_temp": error_temp,
            "valid_llm": valid_llm,
            "value_llm": value_llm,
            "error_llm": error_llm,
            "valid_manual": valid_manual,
            "value_manual": value_manual,
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

    def set_valid_llm(self, field_name: str, value: Optional[str] = None, warning: Optional[str] = None):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = True
        self.fields[field_name]["value_llm"] = value
        self.fields[field_name]["error_llm"] = warning

    def set_invalid_llm(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = False
        self.fields[field_name]["value_llm"] = None
        self.fields[field_name]["error_llm"] = error

    def set_unexpected_error_llm(self, field_name: str, fatal: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_llm"] = None
        self.fields[field_name]["value_llm"] = None
        self.fields[field_name]["error_llm"] = fatal

    def set_valid_manual(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_manual"] = True

    def set_invalid_manual(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid_manual"] = False

    def set_value_manual(self, field_name: str, value: Optional[str]):
        self.ensure_field(field_name)
        self.fields[field_name]["value_manual"] = value

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
                value_llm=parse_dict_field(field_data, "value_llm", exp_type=str, default=None),
                error_llm=parse_dict_field(field_data, "error_llm", exp_type=str, default=None),
                valid_manual=parse_dict_field(field_data, "valid_manual", exp_type=bool, default=None),
                value_manual=parse_dict_field(field_data, "value_manual", exp_type=str, default=None),
            )
        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)


class Validator(BaseModule):
    """Валидация извлечённых RDF-термов."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        tctx = ctx.template_ctx
        if not tctx:
            self.log(WARNING, f'No template found')
            return ModuleResult.failed(message=f"Не удалось загрузить шаблон")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            self.log(WARNING, f'No fields found')
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        extr_res = ExtractionResult.load(doc.extraction_result_file_path())
        if not self._check_field_names_consistency(fields, extr_res):
            self.log(WARNING, f'Field names consistency check failed')
            return ModuleResult.failed(message="Неконсистентность структур. Перезапустите обработку")

        valid_res = self._validate(fields, extr_res)
        valid_res.save(doc.validation_result_file_path())

        if not self._all_fields_validated(valid_res):
            self.log(WARNING, f'Not all fields are validated')
            return ModuleResult.failed(message="Не все поля валидны")

        return ModuleResult.ok()

    def _validate(self, fields: List[Field], extr_res: ExtractionResult) -> ValidationResult:
        result = ValidationResult()
        self._hard_validate(fields, extr_res, result)
        self._validate_with_llm(fields, extr_res, result)
        self._log_result(result, extr_res)
        return result

    def _hard_validate(self, fields: List[Field], extr_res: ExtractionResult, result: ValidationResult):
        for field in fields:
            value = extr_res.get_value_final(field.name)
            try:
                if value is None or not value.strip():
                    result.set_invalid_temp(field.name, "Обязательное поле отсутствует или пустое")
                    continue

                error = field.validator._validate(value)
                if error:
                    result.set_invalid_temp(field.name, error)
                else:
                    result.set_valid_temp(field.name)
            except Exception:
                result.set_invalid_temp(field.name, "Ошибка валидации")

    def _validate_with_llm(self, fields: List[Field], extr_res: ExtractionResult, result: ValidationResult):
        """Валидация и коррекция полей с использованием LLM."""
        try:
            fields_payload = [
                {
                    "name": field.name,
                    "description": field.description,
                    "extraction": {
                        "status": extr_res.is_extracted_final(field.name),
                        "value": extr_res.get_value_final(field.name),
                        "error_temp": extr_res.get_error_temp(field.name),
                        "error_llm": extr_res.get_error_llm(field.name),
                    },
                    "template_validation": {
                        "status": result.is_valid_temp(field.name),
                        "error": result.get_error_temp(field.name),
                    },
                }
                for field in fields
            ]

            system_prompt = read_prompt(VALIDATE_FIELDS_SYS_PROMPT_PATH)
            user_prompt = read_prompt(
                VALIDATE_FIELDS_USER_PROMPT_PATH,
                fields=json.dumps(fields_payload, ensure_ascii=False, indent=2),
            )

            llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
            llm_data = json.loads(llm_raw)
            if not isinstance(llm_data, dict):
                raise ValueError("LLM response must be a dictionary")

            for field in fields:
                item = llm_data.get(field.name)
                if not isinstance(item, dict):
                    result.set_unexpected_error_llm(field.name, "Некорректный формат ответа LLM для поля")
                    continue

                status = parse_dict_field(item, "status", exp_type=bool, default=None)
                value = parse_dict_field(item, "value", exp_type=str, strip_str=True, not_empty=True, default=None)
                error = parse_dict_field(item, "error", exp_type=str, strip_str=True, not_empty=True, default=None)

                if status is None:
                    result.set_unexpected_error_llm(field.name, "Некорректный формат ответа LLM: status должен быть bool")
                    continue

                if status:
                    result.set_valid_llm(field.name, value=value, warning=error)
                else:
                    result.set_invalid_llm(field.name, error or "LLM не смогла провалидировать/исправить значение")

        except Exception:
            self.log(WARNING, "LLM validation level failed", exc_info=True)
            for field in fields:
                data = result.get_field(field.name) or {}
                if data.get("valid_llm") is None:
                    result.set_unexpected_error_llm(field.name, "Непредвиденная ошибка при обработке поля с помощью LLM")

    def _check_field_names_consistency(self, fields: List[Field], extraction_res: ExtractionResult) -> bool:
        template_names = [field.name for field in fields]
        extracted_names = list(extraction_res.fields.keys())
        return set(template_names) == set(extracted_names)

    def _log_result(self, result: ValidationResult, extr_res: ExtractionResult):
        for field_name in result.fields.keys():
            field_label = f"{field_name}:".ljust(LOG_ALIGN_WIDTH)

            extracted_value = extr_res.get_value_final(field_name)
            value_llm = result.get_value_llm(field_name)
            value_manual = result.get_value_manual(field_name)
            final_value = result.get_value_final(field_name, extracted_value)
            error_temp = result.get_error_temp(field_name)
            error_llm = result.get_error_llm(field_name)

            situation = result.get_situation(field_name).full_msg()
            if result.is_valid_final(field_name):
                self.log(INFO, f'{field_label} {situation}: "{final_value or ""}"')
            else:
                parts = [situation]
                if error_temp:
                    parts.append(f"template: {error_temp}")
                if error_llm:
                    parts.append(f"llm: {error_llm}")
                src = f'extracted="{extracted_value}" llm="{value_llm}" manual="{value_manual}"'
                self.log(WARNING, f"{field_label} invalid ({'; '.join(parts)}; {src})")

    def _all_fields_validated(self, result: ValidationResult) -> bool:
        return all(result.is_valid_final(field_name) for field_name in result.fields.keys())
