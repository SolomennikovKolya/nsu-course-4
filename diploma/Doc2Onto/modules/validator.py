import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, Literal, List
from pathlib import Path

from app.openai import ask_gpt, read_prompt
from app.settings import VALIDATE_FIELDS_SYS_PROMPT_PATH, VALIDATE_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from core.document import Document
from core.template.template import Template, Field
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult

HardValidationResult = Dict[str, Dict[str, Optional[str] | bool]]


class FieldValidationData(TypedDict):
    valid: bool
    corrected_value: Optional[str]
    source: Optional[Literal["llm", "human"]]
    error: Optional[str]


class ValidationResult:
    """Результат валидации набора полей"""

    def __init__(self):
        self.fields: Dict[str, FieldValidationData] = {}

    def set_result(
            self, field_name: str, valid: bool,
            corrected_value: Optional[str] = None, source: Optional[Literal["llm", "human"]] = None,
            error: Optional[str] = None):
        self.fields[field_name] = {
            "valid": valid,
            "corrected_value": corrected_value,
            "source": source,
            "error": error,
        }

    def get_error(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error")

    def set_valid(self, field_name: str):
        self.set_result(field_name, True)

    def set_invalid(self, field_name: str, error: str):
        self.set_result(field_name, False, error=error)

    def set_corrected(self, field_name: str, corrected_value: str, source: Literal["llm", "human"], error: Optional[str] = None):
        self.set_result(field_name, True, corrected_value=corrected_value, source=source, error=error)

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
            raw_corrected_value = field_result.get("corrected_value")
            raw_source = field_result.get("source")
            raw_error = field_result.get("error")

            corrected_value = raw_corrected_value if isinstance(raw_corrected_value, str) else None
            source = raw_source if raw_source in ("llm", "human") else None
            error = raw_error if isinstance(raw_error, str) else None
            result.set_result(str(field_name), valid, corrected_value, source, error)

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
            validation_result = self._validate(document, document.template, extraction_result)
            validation_result.save(document.validation_result_file_path())
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _validate(self, document: Document, template: Template, extraction_result: ExtractionResult) -> ValidationResult:
        fields = template.get_fields()
        if not fields:
            raise ValueError("Can't get fields from template")

        if not self._check_field_names_consistency(fields, extraction_result):
            raise ValueError("Field names consistency check failed")

        # Сначала - жёсткая валидация по правилам шаблона
        result = ValidationResult()
        hard_validation = self._hard_validate(fields, extraction_result, result)

        # Затем - валидация и коррекция LLM
        self._validate_with_llm(document, hard_validation, result)

        self._log_validation_result(fields, result)
        return result

    def _hard_validate(self, fields: List[Field], extraction_result: ExtractionResult, result: ValidationResult) -> HardValidationResult:
        hard_validation: HardValidationResult = {}

        for field in fields:
            hard_validation[field.name] = self._hard_validate_field(field, extraction_result, result)

        return hard_validation

    def _hard_validate_field(self, field: Field, extraction_result: ExtractionResult, result: ValidationResult) -> Dict[str, Optional[str] | bool]:
        try:
            value = extraction_result.get_value(field.name)
            if value is None or not value.strip():
                error_text = "Обязательное поле отсутствует или пустое"
                result.set_invalid(field.name, error_text)
                return {
                    "description": field.description,
                    "value": value,
                    "valid": False,
                    "error": error_text,
                }

            message = field.validator._validate(value)
            if message:
                result.set_invalid(field.name, message)
                return {
                    "description": field.description,
                    "value": value,
                    "valid": False,
                    "error": message,
                }

            result.set_valid(field.name)
            return {
                "description": field.description,
                "value": value,
                "valid": True,
                "error": None,
            }

        except Exception:
            error_text = "Ошибка валидации"
            result.set_invalid(field.name, error_text)
            return {
                "description": field.description,
                "value": extraction_result.get_value(field.name),
                "valid": False,
                "error": error_text,
            }

    def _validate_with_llm(self, document: Document, hard_validation: HardValidationResult, result: ValidationResult):
        try:
            document_text = self._read_document_text(document)
            if document_text is None:
                return

            system_prompt = read_prompt(VALIDATE_FIELDS_SYS_PROMPT_PATH)
            user_prompt = read_prompt(
                VALIDATE_FIELDS_USER_PROMPT_PATH,
                document_text=document_text,
                fields=json.dumps(hard_validation, ensure_ascii=False, indent=2),
            )

            llm_data = self._ask_llm_validation(user_prompt, system_prompt)
            if llm_data is None:
                return

            for field_name, raw in llm_data.items():
                if field_name not in hard_validation:
                    continue
                if not isinstance(raw, dict):
                    continue

                status, corrected_value, error = self._parse_llm_field_result(raw)
                if status is None:
                    continue

                self._apply_llm_field_result(result, field_name, status, corrected_value, error)

        except Exception:
            self.log(WARNING, "LLM validation level failed", exc_info=True)

    def _read_document_text(self, document: Document) -> Optional[str]:
        try:
            return document.plain_text_file_path().read_text(encoding="utf-8", errors="strict")
        except Exception:
            return None

    def _ask_llm_validation(self, user_prompt: str, system_prompt: str) -> Optional[dict]:
        llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
        llm_data = json.loads(llm_raw)
        if not isinstance(llm_data, dict):
            raise ValueError("LLM ответ должен быть JSON-словарем")
        return llm_data

    def _parse_llm_field_result(self, raw: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
        status = raw.get("status")
        if status not in ("valid", "corrected", "invalid"):
            return None, None, None

        raw_value = raw.get("value")
        corrected_value = raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None
        raw_error = raw.get("error")
        error = raw_error.strip() if isinstance(raw_error, str) and raw_error.strip() else None
        return status, corrected_value, error

    def _apply_llm_field_result(self, result: ValidationResult, field_name: str, status: str, corrected_value: Optional[str], error: Optional[str]):
        if status == "valid":
            result.set_valid(field_name)
            return

        if status == "corrected":
            if corrected_value is None:
                error_text = self._glue_errors(
                    result.get_error(field_name),
                    error or "LLM вернул status=corrected без значения"
                )
                result.set_invalid(field_name, error_text)
                return

            result.set_corrected(field_name, corrected_value, "llm", error)
            return

        # status == "invalid"
        error_text = self._glue_errors(
            result.get_error(field_name),
            error or "LLM: значение невозможно восстановить"
        )
        result.set_invalid(field_name, error_text)

    def _check_field_names_consistency(self, fields: List[Field], extraction_result: ExtractionResult) -> bool:
        template_names = [field.name for field in fields]
        extracted_names = list(extraction_result.fields.keys())
        return set(template_names) == set(extracted_names)

    def _log_validation_result(self, fields: List[Field], result: ValidationResult):
        for field in fields:
            field_label = f"{field.name}:".ljust(LOG_ALIGN_WIDTH)
            entry = result.fields.get(field.name)
            if not entry:
                self.log(WARNING, f"{field_label} no entry in validation result")
                continue

            if not entry["valid"]:
                error = entry.get("error") or "error not specified"
                self.log(WARNING, f"{field_label} invalid: {error}")
                continue

            corrected = entry.get("corrected_value")
            source = entry.get("source")
            if corrected is None:
                self.log(INFO, f'{field_label} valid')
                continue

            if source == "llm":
                self.log(INFO, f'{field_label} corrected by LLM: "{corrected}"')
            elif source == "human":
                self.log(INFO, f'{field_label} corrected by human: "{corrected}"')
            else:
                self.log(INFO, f'{field_label} valid')

    def _glue_errors(self, prev_err: Optional[str], new_err: Optional[str]) -> Optional[str]:
        if prev_err is None:
            return new_err
        if new_err is None:
            return prev_err
        return f"{prev_err}. {new_err}"
