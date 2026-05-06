import json
from logging import INFO, WARNING
from typing import List

from app.agents import ask_gpt, read_prompt
from app.settings import EXTRACT_FIELDS_SYS_PROMPT_PATH, EXTRACT_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from core.fields.field import Field
from core.uddm.model import UDDM
from models.document import DocumentContext
from models.extraction_result import ExtractionResult
from modules.base import BaseModule, ModuleResult
from utils.general import parse_dict_field


class Extractor(BaseModule):
    """Извлечение полей (индивидуумы + литералы)."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        uddm = ctx.uddm
        if not uddm:
            return ModuleResult.failed(message="Автоматическое извлечение полей невозможно без UDDM")

        tctx = ctx.template_ctx
        if not tctx:
            return ModuleResult.failed(message="Не удалось загрузить шаблон")

        fields = tctx.fields
        if not fields:
            return ModuleResult.failed(message="Не удалось получить поля из кода шаблона")

        ctx.extraction_result = self._extract(fields, uddm)
        ctx.extraction_result.save(doc.extraction_result_file_path())

        return ModuleResult.ok()

    def _extract(self, fields: List[Field], uddm: UDDM) -> ExtractionResult:
        result = ExtractionResult()
        self._extract_fields_declarative(fields, uddm, result)
        self._extract_fields_with_llm(fields, uddm, result)
        self._log_result(result)
        return result

    def _extract_fields_declarative(self, fields: List[Field], uddm: UDDM, result: ExtractionResult):
        for field in fields:
            try:
                text = field.selector._select(uddm)
                if not text:
                    result.set_error_temp(field.name, "Не удалось выделить текст с помощью селектора")
                    continue

                value = field.extractor._extract(text)
                if value is None:
                    result.set_error_temp(field.name, "Не удалось извлечь значение по правилам экстрактора")
                    continue

                result.set_value_temp(field.name, value)

            except Exception:
                result.set_error_temp(field.name, "Непредвиденная ошибка извлечения поля декларативным методом")

    def _extract_fields_with_llm(self, fields: List[Field], uddm: UDDM, result: ExtractionResult):
        try:
            fields_payload = [
                {
                    "name": field.name,
                    "description": field.description,
                    "template": {
                        "status": result.is_extracted_temp(field.name),
                        "value": result.get_value_temp(field.name),
                        "error": result.get_error_temp(field.name),
                    }
                }
                for field in fields
            ]

            system_prompt = read_prompt(EXTRACT_FIELDS_SYS_PROMPT_PATH)
            user_prompt = read_prompt(
                EXTRACT_FIELDS_USER_PROMPT_PATH,
                document_uddm=uddm.to_string(),
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

                template_value = result.get_value_temp(field.name)

                if status and value:
                    # LLM сообщила корректное значение (новое или взамен template).
                    result.set_value_llm(field.name, value, error)
                elif status and value is None and template_value:
                    # LLM подтвердила, что template-значение уже корректно. Берём template как итоговое value_llm, чтобы дальше по пайплайну ходило одно значение.
                    result.set_value_llm(field.name, template_value, None)
                elif status and value is None:
                    # Контракт промпта нарушен: status=true, но и template, и value пустые. Считаем ошибкой.
                    result.set_error_llm(
                        field.name,
                        error or "LLM сообщила об успехе, но не указала значение (нарушен инвариант промпта)",
                    )
                else:
                    # status=false — LLM определила, что значение некорректно или не найдено.
                    result.set_error_llm(field.name, error or "LLM определила, что значение некорректно")

        except Exception:
            self.log(WARNING, "Непредвиденная ошибка при обработке поля с помощью LLM", exc_info=True)
            for field in fields:
                data = result.get_field(field.name) or {}
                if data.get("extracted_llm") is None:
                    result.set_unexpected_error_llm(field.name, "Непредвиденная ошибка при обработке поля с помощью LLM")

    def _log_result(self, result: ExtractionResult):
        for field_name in result.fields.keys():
            field_label = f"{field_name}:".ljust(LOG_ALIGN_WIDTH)

            value = result.get_value_final(field_name)
            error_temp = result.get_error_temp(field_name)
            error_llm = result.get_error_llm(field_name)
            situation = result.get_situation(field_name).short_msg()

            text = f'{field_label} {situation}: "{value}"'
            if error_temp is not None:
                text += f" error_temp: {error_temp}"
            if error_llm is not None:
                text += f" error_llm: {error_llm}"

            self.log(INFO, text)

    def _all_fields_failed(self, result: ExtractionResult) -> bool:
        return all(not result.is_extracted_final(field_name) for field_name in result.fields.keys())
