import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, Literal, List
from pathlib import Path

from app.openai import ask_gpt, read_prompt
from app.settings import EXTRACT_FIELDS_SYS_PROMPT_PATH, EXTRACT_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.template.field import Field
from core.template.template import Template
from core.uddm.model import UDDM


class FieldExtractionData(TypedDict):
    value: Optional[str]                          # Извлеченное значение поля
    source: Optional[Literal["template", "llm"]]  # Источник значения поля
    error: Optional[str]                          # Ошибка извлечения значения поля (если значение не извлечено)


class ExtractionResult:
    """
    Результат извлечения полей документа.
    Словарь вида {field_name: FieldExtractionData}
    """

    def __init__(self):
        self.fields: Dict[str, FieldExtractionData] = {}

    def get_value(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value")

    def get_error(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error")

    def get_source(self, field_name: str) -> Optional[Literal["template", "llm"]]:
        return self.fields.get(field_name, {}).get("source")

    def set_result(
            self, field_name: str,
            value: Optional[str], source: Optional[Literal["template", "llm"]] = None,
            error: Optional[str] = None):
        self.fields[field_name] = {
            "value": value,
            "source": source,
            "error": error,
        }

    def set_from_template(self, field_name: str, value: Optional[str], error: Optional[str] = None):
        self.set_result(field_name, value, "template", error)

    def set_from_llm(self, field_name: str, value: Optional[str], error: Optional[str] = None):
        self.set_result(field_name, value, "llm", error)

    @staticmethod
    def load(path: Path) -> "ExtractionResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid extraction result file: {path}")

            result = ExtractionResult()
            for field_name, field_value in data.items():
                if not isinstance(field_name, str):
                    raise ValueError(f"Invalid field name in extraction result file: {path}")

                if not isinstance(field_value, dict):
                    raise ValueError(f"Invalid value in extraction result file: {path}")

                raw_value = field_value.get("value")
                raw_source = field_value.get("source")
                raw_error = field_value.get("error")

                value = raw_value if isinstance(raw_value, str) else None
                source = raw_source if isinstance(raw_source, str) and raw_source in ("template", "llm") else None
                error = raw_error if isinstance(raw_error, str) else None
                result.set_result(field_name, value, source, error)

            return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)


class Extractor(BaseModule):
    """Извлечение RDF-термов (индивидуумы + литералы)."""

    def __init__(self):
        super().__init__()

    def execute(self, document: Document) -> ModuleResult:
        try:
            if not document.uddm:
                self.log(WARNING, f"No UDDM found")
                return ModuleResult.FAILED

            if not document.doc_class or not document.template:
                self.log(WARNING, f"No template found")
                return ModuleResult.FAILED

            if not document.template.code:
                self.log(WARNING, f"Template {document.template.name} has no code")
                return ModuleResult.FAILED

            extraction_result = self._extract(document, document.template, document.uddm)
            extraction_result.save(document.extraction_result_file_path())
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _extract(self, document: Document, template: Template, uddm: UDDM) -> ExtractionResult:
        if not template.fields:
            template.fields = template.code.fields()

        result = ExtractionResult()
        self._extract_fields_declarative(template, uddm, result)

        missing_fields = [field for field in template.fields if result.get_value(field.name) is None]
        if not missing_fields:
            self._log_result(template, result)
            return result

        self._extract_fields_llm(document, template, missing_fields, result)
        self._log_result(template, result)
        return result

    def _extract_fields_declarative(self, template: Template, uddm: UDDM, result: ExtractionResult):
        """Первый уровень: Декларативное извлечение полей."""
        for field in template.fields:
            try:
                text = field.selector._select(uddm)
                if not text:
                    result.set_from_template(field.name, None, "Не удалось выделить текст с помощью селектора")
                    continue

                value = field.extractor._extract(text)
                if value is None:
                    result.set_from_template(field.name, None, "Не удалось извлечь значение по правилам экстрактора")
                    continue

                result.set_from_template(field.name, value)

            except Exception:
                result.set_from_template(field.name, None, "Ошибка извлечения поля декларативным методом")

    def _extract_fields_llm(self, document: Document, template: Template, missing_fields: List[Field], result: ExtractionResult):
        """Второй уровень: Извлечение с использованием LLM."""
        try:
            uddm_text = document.uddm_tree_view_file_path().read_text(encoding="utf-8", errors="strict")
            plain_text = document.plain_text_file_path().read_text(encoding="utf-8", errors="strict")
            fields_desc = "\n".join(
                f'- "{field.name}": {field.description}'
                for field in missing_fields
            )

            user_prompt = read_prompt(
                EXTRACT_FIELDS_USER_PROMPT_PATH,
                document_uddm=uddm_text,
                document_text=plain_text,
                template_description=template.description or "",
                fields=fields_desc,
            )
            system_prompt = read_prompt(EXTRACT_FIELDS_SYS_PROMPT_PATH)

            llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
            llm_data = json.loads(llm_raw)
            if not isinstance(llm_data, dict):
                raise ValueError("LLM ответ должен быть JSON-словарем")

            for field in missing_fields:
                llm_value = llm_data.get(field.name)
                if isinstance(llm_value, str) and llm_value.strip():
                    result.set_from_llm(field.name, llm_value.strip())
                else:
                    error = self._glue_errors(result.get_error(field.name), "LLM не смогла извлечь значение")
                    result.set_result(field.name, None, None, error)

        except Exception:
            self.log(WARNING, "LLM fallback failed", exc_info=True)
            for field in missing_fields:
                if result.get_value(field.name) is None:
                    error_text = self._glue_errors(
                        result.get_error(field.name),
                        "Непредвиденная ошибка при извлечении поля с помощью LLM"
                    )
                    result.set_result(field.name, None, None, error_text)

    def _log_result(self, template: Template, result: ExtractionResult):
        if not template.fields:
            return

        for field in template.fields:
            field_label = f"{field.name}:".ljust(LOG_ALIGN_WIDTH)
            value = result.get_value(field.name)
            source = result.get_source(field.name)
            error = result.get_error(field.name)

            if value is not None:
                if source == "llm":
                    self.log(INFO, f'{field_label} "{value}" (extracted by LLM)')
                else:
                    self.log(INFO, f'{field_label} "{value}"')
            else:
                source_label = f", source={source}" if source else ""
                error_text = error or "value is missing"
                self.log(WARNING, f"{field_label} None ({error_text}{source_label})")

    def _glue_errors(self, prev_err: Optional[str], new_err: Optional[str]) -> Optional[str]:
        if prev_err is None:
            return new_err
        if new_err is None:
            return prev_err
        return f"{prev_err}. {new_err}"
