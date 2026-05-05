import json
from logging import INFO, WARNING
from typing import List

from app.agents import ask_gpt, read_prompt
from app.utils import parse_dict_field
from app.settings import VALIDATE_FIELDS_SYS_PROMPT_PATH, VALIDATE_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from core.template.field import Field
from models.document import DocumentContext
from models.extraction_result import ExtractionResult
from models.validation_result import ValidationResult
from modules.base import BaseModule, ModuleResult


class Validator(BaseModule):
    """Валидация извлечённых RDF-термов."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        tctx = ctx.template_ctx
        if not tctx:
            return ModuleResult.failed(message=f"Не удалось загрузить шаблон")

        fields = tctx.fields
        if fields is None or len(fields) == 0:
            return ModuleResult.failed(message=f"Шаблон не имеет полей")

        extr_res = ctx.extraction_result
        if not extr_res:
            return ModuleResult.failed(message="Не удалось загрузить результат извлечения")

        ctx.validation_result = self._validate(fields, extr_res)
        ctx.validation_result.save(doc.validation_result_file_path())

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
                    result.set_invalid_temp(field.name, "Поле отсутствует или пустое")
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
                    "value": extr_res.get_value_final(field.name),
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
                error = parse_dict_field(item, "error", exp_type=str, strip_str=True, not_empty=True, default=None)

                if status is None:
                    result.set_unexpected_error_llm(field.name, "Некорректный формат ответа LLM: status должен быть bool")
                    continue

                if status:
                    result.set_valid_llm(field.name)
                else:
                    result.set_invalid_llm(field.name, error or "LLM определила, что значение некорректно")

        except Exception:
            self.log(WARNING, "Непредвиденная ошибка при обработке поля с помощью LLM", exc_info=True)
            for field in fields:
                data = result.get_field(field.name) or {}
                if data.get("valid_llm") is None:
                    result.set_unexpected_error_llm(field.name, "Непредвиденная ошибка при обработке поля с помощью LLM")

    def _log_result(self, result: ValidationResult, extr_res: ExtractionResult):
        for field_name in result.fields.keys():
            field_label = f"{field_name}:".ljust(LOG_ALIGN_WIDTH)

            value = extr_res.get_value_final(field_name)
            error_temp = result.get_error_temp(field_name)
            error_llm = result.get_error_llm(field_name)
            situation = result.get_situation(field_name).short_msg()

            text = f'{field_label} {situation}: "{value}"'
            if error_temp is not None:
                text += f" error_temp: {error_temp}"
            if error_llm is not None:
                text += f" error_llm: {error_llm}"

            self.log(INFO, text)

    def _all_fields_validated(self, result: ValidationResult) -> bool:
        return all(result.is_valid_final(field_name) for field_name in result.fields.keys())
