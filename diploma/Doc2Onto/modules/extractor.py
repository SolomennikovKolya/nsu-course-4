import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, Literal
from pathlib import Path

from app.openai import ask_gpt, read_prompt
from app.settings import EXTRACT_FIELDS_SYS_PROMPT_PATH, EXTRACT_FIELDS_USER_PROMPT_PATH
from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.template.template import Template
from core.uddm.model import UDDM


class FieldExtractionData(TypedDict):
    value: Optional[str]
    error: Optional[str]
    source: Literal["template", "llm"]


class ExtractionResult:
    """
    Результат извлечения полей документа.
    Словарь вида {field_name: {"value":..., "error":..., "source":...}}
    """

    def __init__(self):
        self.fields: Dict[str, FieldExtractionData] = {}

    def get_value(self, field_name: str) -> Optional[str]:
        data = self.fields.get(field_name)
        return data.get("value") if data else None

    def get_error(self, field_name: str) -> Optional[str]:
        data = self.fields.get(field_name)
        return data.get("error") if data else None

    def get_source(self, field_name: str) -> Optional[Literal["template", "llm"]]:
        data = self.fields.get(field_name)
        return data.get("source") if data else None

    def set_result(
            self, field_name: str, value: Optional[str],
            error: Optional[str] = None, source: Literal["template", "llm"] = "template"):
        self.fields[field_name] = {
            "value": value,
            "error": error,
            "source": source,
        }

    def set_from_template(self, field_name: str, value: Optional[str], error: Optional[str] = None):
        self.set_result(field_name, value, error, "template")

    def set_from_llm(self, field_name: str, value: Optional[str], error: Optional[str] = None):
        self.set_result(field_name, value, error, "llm")

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
                raw_error = field_value.get("error")
                raw_source = field_value.get("source")

                value = raw_value if isinstance(raw_value, str) else None
                error = raw_error if isinstance(raw_error, str) else None
                source = raw_source if raw_source in ("template", "llm") else "template"
                result.set_result(field_name, value, error, source)

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

        ALIGN_WIDTH = 30
        result = ExtractionResult()

        # ----- Декларативное извлечение полей -----

        for field in template.fields:
            try:
                field_label = f"{field.name}:".ljust(ALIGN_WIDTH)
                text = field.selector._select(uddm)
                if not text:
                    result.set_from_template(field.name, None, "Не удалось выделить текст с помощью селектора")
                    self.log(WARNING, f"{field_label} None (error selecting text)")
                    continue

                value = field.extractor._extract(text)
                if value is None:
                    result.set_from_template(field.name, None, "Не удалось извлечь значение по правилам экстрактора")
                    self.log(WARNING, f"{field_label} None (error extracting value)")
                    continue

                result.set_from_template(field.name, value)
                self.log(INFO, f'{field_label} "{value}"')

            except Exception:
                field_label = f"{field.name}:".ljust(ALIGN_WIDTH)
                result.set_from_template(field.name, None, "Ошибка извлечения поля декларативным методом")
                self.log(WARNING, f"{field_label} None (error extracting field)", exc_info=True)

        # ----- Извлечение с использованием LLM -----

        missing_fields = [field for field in template.fields if result.get_value(field.name) is None]
        if not missing_fields:
            return result

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
                field_label = f"{field.name}:".ljust(ALIGN_WIDTH)
                llm_value = llm_data.get(field.name)
                if isinstance(llm_value, str) and llm_value.strip():
                    value = llm_value.strip()
                    result.set_from_llm(field.name, value)
                    self.log(INFO, f'{field_label} "{value}" (extracted by LLM)')
                else:
                    result.set_from_llm(field.name, None, "LLM не смог извлечь значение")
                    self.log(WARNING, f"{field_label} None (llm fallback failed)")

        except Exception:
            self.log(WARNING, "LLM fallback failed", exc_info=True)
            for field in missing_fields:
                if result.get_value(field.name) is None:
                    result.set_from_llm(field.name, None, "Ошибка LLM fallback")

        return result
