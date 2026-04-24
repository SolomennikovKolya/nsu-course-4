import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, List
from pathlib import Path

from app.agents import ask_gpt, read_prompt
from app.settings import VALIDATE_FIELDS_SYS_PROMPT_PATH, VALIDATE_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from core.document import Document, DocumentContext
from core.template.field import Field
from modules.base import BaseModule, ModuleResult
from modules.extractor import ExtractionResult

HardValidationResult = Dict[str, Dict[str, Optional[str] | bool]]


class FieldValidationData(TypedDict):
    valid: bool                            # Итоговая валидность после всех уровней
    extracted_value: Optional[str]         # Значение из ExtractionResult, для которого проводилась валидация
    error_temp: Optional[str]              # Ошибка жёсткой (template) валидации
    corrected_value_llm: Optional[str]     # Значение после LLM-коррекции (если было)
    error_llm: Optional[str]               # Ошибка LLM-валидации/коррекции (если была)
    corrected_value_manual: Optional[str]  # Ручная правка (позже через UI)


class ValidationResult:
    """Результат валидации набора полей"""

    def __init__(self):
        self.fields: Dict[str, FieldValidationData] = {}

    def is_valid(self, field_name: str) -> bool:
        return self.fields.get(field_name, {}).get("valid", False)

    def is_all_valid(self) -> bool:
        return all(field["valid"] for field in self.fields.values())

    def get_extracted_value(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("extracted_value")

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_corrected_value_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("corrected_value_llm")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    def get_corrected_value_manual(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("corrected_value_manual")

    def set_result(
            self,
            field_name: str,
            *,
            valid: bool = False,
            extracted_value: Optional[str] = None,
            error_temp: Optional[str] = None,
            corrected_value_llm: Optional[str] = None,
            error_llm: Optional[str] = None,
            corrected_value_manual: Optional[str] = None
    ):
        self.fields[field_name] = {
            "valid": valid,
            "extracted_value": extracted_value,
            "error_temp": error_temp,
            "corrected_value_llm": corrected_value_llm,
            "error_llm": error_llm,
            "corrected_value_manual": corrected_value_manual,
        }

    def ensure_field(self, field_name: str):
        if field_name in self.fields:
            return

        self.set_result(field_name)

    def set_extracted_value(self, field_name: str, extracted_value: Optional[str]):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted_value"] = extracted_value

    def set_valid_temp(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = True
        self.fields[field_name]["error_temp"] = None

    def set_invalid_temp(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = False
        self.fields[field_name]["error_temp"] = error

    def set_valid_llm(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = True
        self.fields[field_name]["error_llm"] = None

    def set_invalid_llm(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = False
        self.fields[field_name]["error_llm"] = error

    def set_llm_corrected(self, field_name: str, corrected_value: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = True
        self.fields[field_name]["corrected_value_llm"] = corrected_value

    def set_valid_manual(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = True

    def set_invalid_manual(self, field_name: str):
        self.ensure_field(field_name)
        self.fields[field_name]["valid"] = False

    def set_corrected_value_manual(self, field_name: str, corrected_value: Optional[str]):
        self.ensure_field(field_name)
        self.fields[field_name]["corrected_value_manual"] = corrected_value

    @staticmethod
    def load(path: Path) -> "ValidationResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid validation result file: {path}")

        result = ValidationResult()
        for field_name, field_data in data.items():
            if not isinstance(field_data, dict):
                continue

            valid = bool(field_data.get("valid", False))
            extracted_value = field_data.get("extracted_value")
            error_temp = field_data.get("error_temp")
            corrected_value_llm = field_data.get("corrected_value_llm")
            error_llm = field_data.get("error_llm")
            corrected_value_manual = field_data.get("corrected_value_manual")

            result.set_result(
                field_name,
                valid=valid,
                extracted_value=extracted_value if isinstance(extracted_value, str) else None,
                error_temp=error_temp if isinstance(error_temp, str) else None,
                corrected_value_llm=corrected_value_llm if isinstance(corrected_value_llm, str) else None,
                error_llm=error_llm if isinstance(error_llm, str) else None,
                corrected_value_manual=corrected_value_manual if isinstance(corrected_value_manual, str) else None,
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
            self.log(WARNING, f'Template "{doc.doc_class}" not found')
            return ModuleResult.failed(message=f"Не удалось загрузить шаблон")

        code = tctx.code
        if not code:
            self.log(WARNING, f'Template "{tctx.template.name}" has no code')
            return ModuleResult.failed(message=f"Шаблон не имеет кода")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            self.log(WARNING, f'Template "{tctx.template.name}" has no fields')
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        extr_res = ExtractionResult.load(doc.extraction_result_file_path())
        if not self._check_field_names_consistency(fields, extr_res):
            self.log(WARNING, f'Field names consistency check failed for template "{tctx.template.name}"')
            return ModuleResult.failed(message="Неконсистентность структур: "
                                       "набор полей после экстракции и в шаблоне не совпадает."
                                       "Перезапустите обработку")

        valid_res = self._validate(doc, fields, extr_res)
        valid_res.save(doc.validation_result_file_path())

        if not self._all_fields_validated(valid_res):
            self.log(WARNING, f'Not all fields are validated for template "{tctx.template.name}"')
            return ModuleResult.failed(message="Не все поля валидны")

        return ModuleResult.ok()

    def _validate(self, doc: Document, fields: List[Field], extraction_res: ExtractionResult) -> ValidationResult:
        result = ValidationResult()
        for field in fields:
            result.set_extracted_value(field.name, extraction_res.get_value(field.name))

        hard_validation = self._hard_validate(fields, extraction_res, result)
        self._validate_with_llm(doc, hard_validation, result)

        self._log_result(result)
        return result

    def _hard_validate(self, fields: List[Field], extr_res: ExtractionResult, result: ValidationResult) -> HardValidationResult:
        """Жёсткая валидация полей декларативным методом."""
        hard_validation: HardValidationResult = {}

        for field in fields:
            extracted_value = extr_res.get_value(field.name)
            hard_validation[field.name] = self._hard_validate_field(field, extracted_value, result)

        return hard_validation

    def _hard_validate_field(self, field: Field, extracted_value: Optional[str], result: ValidationResult) -> Dict[str, Optional[str] | bool]:
        try:
            if extracted_value is None or not extracted_value.strip():
                error_text = "Обязательное поле отсутствует или пустое"
                result.set_invalid_temp(field.name, error_text)
                return {
                    "description": field.description,
                    "value": extracted_value,
                    "valid": False,
                    "error": error_text,
                }

            message = field.validator._validate(extracted_value)
            if message:
                result.set_invalid_temp(field.name, message)
                return {
                    "description": field.description,
                    "value": extracted_value,
                    "valid": False,
                    "error": message,
                }

            result.set_valid_temp(field.name)
            return {
                "description": field.description,
                "value": extracted_value,
                "valid": True,
                "error": None,
            }

        except Exception:
            error_text = "Ошибка валидации"
            result.set_invalid_temp(field.name, error_text)
            return {
                "description": field.description,
                "value": extracted_value,
                "valid": False,
                "error": error_text,
            }

    def _validate_with_llm(self, doc: Document, hard_validation: HardValidationResult, result: ValidationResult):
        """Валидация и коррекция полей с использованием LLM."""
        try:
            system_prompt = read_prompt(VALIDATE_FIELDS_SYS_PROMPT_PATH)

            uddm_text = doc.uddm_file_path().read_text(encoding="utf-8", errors="strict")
            user_prompt = read_prompt(
                VALIDATE_FIELDS_USER_PROMPT_PATH,
                document_uddm_text=uddm_text,
                fields=json.dumps(hard_validation, ensure_ascii=False, indent=2),
            )

            llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
            llm_data = json.loads(llm_raw)
            if not isinstance(llm_data, dict):
                raise ValueError("LLM response must be a dictionary")

            for field_name, raw in llm_data.items():
                if field_name not in hard_validation or not isinstance(raw, dict):
                    continue

                status, corrected_value, error = self._parse_llm_field_result(raw)
                if status is None:
                    continue

                self._apply_llm_field_result(result, field_name, status, corrected_value, error)

        except Exception:
            self.log(WARNING, "LLM validation level failed", exc_info=True)

    def _parse_llm_field_result(self, raw: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
        status = raw.get("status")
        if status not in ("valid", "corrected", "invalid"):
            return None, None, None

        raw_value = raw.get("corrected_value")
        corrected_value = raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None

        raw_error = raw.get("error")
        error = raw_error.strip() if isinstance(raw_error, str) and raw_error.strip() else None
        return status, corrected_value, error

    def _apply_llm_field_result(
            self, result: ValidationResult, field_name: str,
            status: str, corrected_value: Optional[str], error: Optional[str]
    ):
        if status == "valid":
            # Если поле было валидно изначально, то оставляем его валидным
            # Если поле было невалидно изначально, то оставляем его невалидным (так как LLM не смог исправить его, но вернул status=valid)
            pass
        elif status == "corrected":
            if corrected_value is None:
                result.set_invalid_llm(field_name, error or "LLM вернул status=corrected без значения")
            else:
                result.set_llm_corrected(field_name, corrected_value)
        else:
            result.set_invalid_llm(field_name, error or "LLM: значение невозможно восстановить")

    def _check_field_names_consistency(self, fields: List[Field], extraction_res: ExtractionResult) -> bool:
        template_names = [field.name for field in fields]
        extracted_names = list(extraction_res.fields.keys())
        return set(template_names) == set(extracted_names)

    def _log_result(self, result: ValidationResult):
        for field_name in result.fields.keys():
            field_label = f"{field_name}:".ljust(LOG_ALIGN_WIDTH)

            extracted_value = result.get_extracted_value(field_name)
            error_temp = result.get_error_temp(field_name)
            corrected_llm = result.get_corrected_value_llm(field_name)
            error_llm = result.get_error_llm(field_name)
            corrected_manual = result.get_corrected_value_manual(field_name)

            final_value = corrected_manual or corrected_llm or extracted_value

            if result.is_valid(field_name):
                if corrected_manual is not None:
                    self.log(INFO, f'{field_label} valid (manual): "{corrected_manual}"')
                elif corrected_llm is not None:
                    before = extracted_value or ""
                    before_shown = before if before.strip() else "(пусто)"
                    self.log(INFO, f'{field_label} valid (llm corrected): "{before_shown}" -> "{corrected_llm}"')
                else:
                    self.log(INFO, f'{field_label} valid: "{final_value or ""}"')
            else:
                parts = []
                if error_temp:
                    parts.append(f"template: {error_temp}")
                if error_llm:
                    parts.append(f"llm: {error_llm}")
                if not parts:
                    parts.append("error not specified")
                self.log(WARNING, f"{field_label} invalid ({'; '.join(parts)})")

    def _all_fields_validated(self, result: ValidationResult) -> bool:
        return all(result.is_valid(field_name) for field_name in result.fields.keys())
