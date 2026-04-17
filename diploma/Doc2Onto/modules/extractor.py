import json
from logging import WARNING, INFO
from typing import Dict, Optional, TypedDict, List
from pathlib import Path

from app.agents import ask_gpt, read_prompt
from app.settings import EXTRACT_FIELDS_SYS_PROMPT_PATH, EXTRACT_FIELDS_USER_PROMPT_PATH, LOG_ALIGN_WIDTH
from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.template.field import Field
from core.template.template import Template
from core.uddm.model import UDDM


class FieldExtractionData(TypedDict):
    extracted: bool              # Итоговый успех/неудача извлечения поля
    value_temp: Optional[str]    # Значение, извлечённое по шаблону
    error_temp: Optional[str]    # Ошибка шаблонного извлечения
    value_llm: Optional[str]     # Значение, извлечённое LLM (fallback)
    error_llm: Optional[str]     # Ошибка LLM-извлечения (fallback)


class ExtractionResult:
    """
    Результат извлечения полей документа.
    Словарь вида {field_name: FieldExtractionData}
    """

    def __init__(self):
        self.fields: Dict[str, FieldExtractionData] = {}

    def is_extracted(self, field_name: str) -> bool:
        return bool(self.fields.get(field_name, {}).get("extracted", False))

    def get_value(self, field_name: str) -> Optional[str]:
        data = self.fields.get(field_name)
        if not data:
            return None
        return data.get("value_llm") or data.get("value_temp")

    def get_value_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_temp")

    def get_error_temp(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_temp")

    def get_value_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("value_llm")

    def get_error_llm(self, field_name: str) -> Optional[str]:
        return self.fields.get(field_name, {}).get("error_llm")

    def set_result(
            self,
            field_name: str,
            *,
            extracted: bool = False,
            value_temp: Optional[str] = None,
            error_temp: Optional[str] = None,
            value_llm: Optional[str] = None,
            error_llm: Optional[str] = None
    ):
        self.fields[field_name] = {
            "extracted": extracted,
            "value_temp": value_temp,
            "error_temp": error_temp,
            "value_llm": value_llm,
            "error_llm": error_llm,
        }

    def ensure_field(self, field_name: str):
        if field_name in self.fields:
            return

        self.set_result(field_name)

    def set_value_temp(self, field_name: str, value: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted"] = True
        self.fields[field_name]["value_temp"] = value
        self.fields[field_name]["error_temp"] = None

    def set_error_temp(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted"] = False
        self.fields[field_name]["value_temp"] = None
        self.fields[field_name]["error_temp"] = error

    def set_value_llm(self, field_name: str, value: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted"] = True
        self.fields[field_name]["value_llm"] = value
        self.fields[field_name]["error_llm"] = None

    def set_error_llm(self, field_name: str, error: str):
        self.ensure_field(field_name)
        self.fields[field_name]["extracted"] = False
        self.fields[field_name]["value_llm"] = None
        self.fields[field_name]["error_llm"] = error

    @staticmethod
    def load(path: Path) -> "ExtractionResult":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid extraction result file: {path}")

        result = ExtractionResult()
        for field_name, field_data in data.items():
            if not isinstance(field_name, str):
                raise ValueError(f"Invalid field name in extraction result file: {path}")

            if not isinstance(field_data, dict):
                raise ValueError(f"Invalid value in extraction result file: {path}")

            extracted = bool(field_data.get("extracted", False))
            value_temp = field_data.get("value_temp")
            error_temp = field_data.get("error_temp")
            value_llm = field_data.get("value_llm")
            error_llm = field_data.get("error_llm")

            result.set_result(
                field_name,
                extracted=extracted,
                value_temp=value_temp if isinstance(value_temp, str) else None,
                error_temp=error_temp if isinstance(error_temp, str) else None,
                value_llm=value_llm if isinstance(value_llm, str) else None,
                error_llm=error_llm if isinstance(error_llm, str) else None,
            )
        return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)


class Extractor(BaseModule):
    """Извлечение полей (индивидуумы + литералы)."""

    def __init__(self):
        super().__init__()

    def execute(self, document: Document) -> ModuleResult:
        try:
            uddm = UDDM.load(document.uddm_file_path())
            if not uddm:
                self.log(WARNING, f"No UDDM found")
                return ModuleResult.FAILED

            if not document.doc_class or not document.template:
                self.log(WARNING, f"No template found")
                return ModuleResult.FAILED

            if not document.template.code:
                self.log(WARNING, f"Template {document.template.name} has no code")
                return ModuleResult.FAILED

            extraction_result = self._extract(document, document.template, uddm)
            extraction_result.save(document.extraction_result_file_path())
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _extract(self, document: Document, template: Template, uddm: UDDM) -> ExtractionResult:
        fields = template.get_fields()
        if not fields:
            raise ValueError("Can't get fields from template")

        result = ExtractionResult()
        self._extract_fields_declarative(fields, uddm, result)

        missing_fields = [field for field in fields if not result.is_extracted(field.name)]
        if not missing_fields:
            self._log_result(result)
            return result

        self._extract_fields_llm(document, template, missing_fields, result)
        self._log_result(result)
        return result

    def _extract_fields_declarative(self, fields: List[Field], uddm: UDDM, result: ExtractionResult):
        """Первый уровень: Декларативное извлечение полей."""
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
                result.set_error_temp(field.name, "Ошибка извлечения поля декларативным методом")

    def _extract_fields_llm(self, document: Document, template: Template, missing_fields: List[Field], result: ExtractionResult):
        """Второй уровень: Извлечение с использованием LLM."""
        try:
            system_prompt = read_prompt(EXTRACT_FIELDS_SYS_PROMPT_PATH)

            uddm_text = document.uddm_tree_view_file_path().read_text(encoding="utf-8", errors="strict")
            fields_desc = "\n".join(
                f'- "{field.name}": {field.description}'
                for field in missing_fields
            )
            user_prompt = read_prompt(
                EXTRACT_FIELDS_USER_PROMPT_PATH,
                document_text=uddm_text,
                template_description=template.description or "",
                fields=fields_desc,
            )

            llm_raw = ask_gpt(user_prompt, system_prompt=system_prompt)
            llm_data = json.loads(llm_raw)
            if not isinstance(llm_data, dict):
                raise ValueError("LLM response must be a dictionary")

            for field in missing_fields:
                llm_value = llm_data.get(field.name)
                if isinstance(llm_value, str) and llm_value.strip():
                    result.set_value_llm(field.name, llm_value.strip())
                else:
                    result.set_error_llm(field.name, "LLM не смогла извлечь значение")

        except Exception:
            self.log(WARNING, "Unexpected error in LLM fallback", exc_info=True)
            for field in missing_fields:
                if not result.is_extracted(field.name):
                    result.set_error_llm(field.name, "Непредвиденная ошибка при извлечении поля с помощью LLM")

    def _log_result(self, result: ExtractionResult):
        for field_name in result.fields.keys():
            field_label = f"{field_name}:".ljust(LOG_ALIGN_WIDTH)

            extracted = result.is_extracted(field_name)
            value = result.get_value(field_name)
            value_temp = result.get_value_temp(field_name)
            value_llm = result.get_value_llm(field_name)
            error_temp = result.get_error_temp(field_name)
            error_llm = result.get_error_llm(field_name)

            if extracted and value is not None:
                if value_llm is not None:
                    self.log(INFO, f'{field_label} "{value}" (extracted by LLM)')
                else:
                    self.log(INFO, f'{field_label} "{value}"')
            else:
                err_parts = []
                if error_temp:
                    err_parts.append(f"template: {error_temp}")
                if error_llm:
                    err_parts.append(f"llm: {error_llm}")
                if not err_parts:
                    err_parts.append("value is missing")

                temp_part = f'temp="{value_temp}"' if value_temp is not None else "temp=null"
                llm_part = f'llm="{value_llm}"' if value_llm is not None else "llm=null"
                self.log(WARNING, f"{field_label} None ({'; '.join(err_parts)}; {temp_part}; {llm_part})")
