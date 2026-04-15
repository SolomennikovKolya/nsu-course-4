import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, Literal
from pathlib import Path

from app.openai import ask_gpt, read_prompt
from app.settings import VALIDATE_FIELDS_SYS_PROMPT_PATH, VALIDATE_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from core.document import Document
from core.template.template import Template
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult


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
        if not template.fields:
            template.fields = template.code.fields()

        self._validate_field_names_consistency(template, extraction_result)

        result = ValidationResult()
        hard_validation = self._hard_validate(template, extraction_result, result)

        self._validate_with_llm(document, hard_validation, result)
        self._log_validation_result(template, result)
        return result

    def _validate_field_names_consistency(self, template: Template, extraction_result: ExtractionResult):
        template_names = [field.name for field in (template.fields or [])]
        extracted_names = list(extraction_result.fields.keys())
        if set(template_names) != set(extracted_names):
            raise ValueError(
                "Несовпадение набора полей template/extraction_result: "
                f"template={template_names}, extraction={extracted_names}"
            )

    def _hard_validate(self, template: Template, extraction_result: ExtractionResult,
                       result: ValidationResult) -> Dict[str, Dict[str, Optional[str] | bool]]:
        """Первый уровень: жёсткая валидация правилами."""
        hard_validation: Dict[str, Dict[str, Optional[str] | bool]] = {}

        for field in template.fields:
            try:
                value = extraction_result.get_value(field.name)
                if value is None or not value.strip():
                    error_text = "Обязательное поле отсутствует или пустое"
                    result.set_invalid(field.name, error_text)
                    hard_validation[field.name] = {
                        "description": field.description,
                        "value": value,
                        "valid": False,
                        "error": error_text,
                    }
                    continue

                message = field.validator._validate(value)
                if message:
                    result.set_invalid(field.name, message)
                    hard_validation[field.name] = {
                        "description": field.description,
                        "value": value,
                        "valid": False,
                        "error": message,
                    }
                    continue

                result.set_valid(field.name)
                hard_validation[field.name] = {
                    "description": field.description,
                    "value": value,
                    "valid": True,
                    "error": None,
                }

            except Exception:
                error_text = "Ошибка валидации"
                result.set_invalid(field.name, error_text)
                hard_validation[field.name] = {
                    "description": field.description,
                    "value": extraction_result.get_value(field.name),
                    "valid": False,
                    "error": error_text,
                }

        return hard_validation

    def _validate_with_llm(self, document: Document, hard_validation: Dict[str, Dict[str, Optional[str] | bool]], result: ValidationResult):
        """Второй уровень: обязательная валидация/коррекция LLM."""
        try:
            document_text = document.plain_text_file_path().read_text(encoding="utf-8", errors="strict")

            system_prompt = read_prompt(VALIDATE_FIELDS_SYS_PROMPT_PATH)
            user_prompt = read_prompt(
                VALIDATE_FIELDS_USER_PROMPT_PATH,
                document_text=document_text,
                fields=json.dumps(hard_validation, ensure_ascii=False, indent=2),
            )

            llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
            llm_data = json.loads(llm_raw)
            if not isinstance(llm_data, dict):
                raise ValueError("LLM ответ должен быть JSON-словарем")

            for field_name, raw in llm_data.items():
                if field_name not in hard_validation or not isinstance(raw, dict):
                    continue

                raw_value = raw.get("value")
                raw_error = raw.get("error")

                status = raw.get("status")
                corrected_value = raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None
                error = raw_error.strip() if isinstance(raw_error, str) and raw_error.strip() else None

                if status == "valid":
                    result.set_valid(field_name)
                elif status == "corrected":
                    if corrected_value is None:
                        error_text = self._glue_errors(
                            result.get_error(field_name),
                            error or "LLM вернул status=corrected без значения"
                        )
                        result.set_invalid(field_name, error_text)
                    else:
                        result.set_corrected(field_name, corrected_value, "llm", error)
                elif status == "invalid":
                    error_text = self._glue_errors(
                        result.get_error(field_name),
                        error or "LLM: значение невозможно восстановить"
                    )
                    result.set_invalid(field_name, error_text)

        except Exception:
            self.log(WARNING, "LLM validation level failed", exc_info=True)

    def _log_validation_result(self, template: Template, result: ValidationResult):
        """Одна строка на поле: итог после жёсткой валидации и LLM."""
        for field in template.fields:
            field_label = f"{field.name}:".ljust(LOG_ALIGN_WIDTH)
            entry = result.fields.get(field.name)
            if not entry:
                self.log(WARNING, f"{field_label} no entry in validation result")
                continue

            valid = entry["valid"]
            corrected = entry.get("corrected_value")
            source = entry.get("source")
            error = entry.get("error")

            if valid:
                if corrected is not None and source == "llm":
                    self.log(INFO, f'{field_label} corrected by LLM: "{corrected}"')
                elif corrected is not None and source == "human":
                    self.log(INFO, f'{field_label} corrected by human: "{corrected}"')
                else:
                    self.log(INFO, f'{field_label} valid')
            else:
                self.log(WARNING, f"{field_label} invalid: {error or 'error not specified'}")

    def _glue_errors(self, prev_err: Optional[str], new_err: Optional[str]) -> Optional[str]:
        if prev_err is None:
            return new_err
        if new_err is None:
            return prev_err
        return f"{prev_err}. {new_err}"
