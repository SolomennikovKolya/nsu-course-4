import json
from logging import WARNING, INFO
from typing import Dict, Optional
from pathlib import Path

from modules.base import BaseModule, ModuleResult
from core.document import Document
from core.template.template import Template
from core.uddm.model import UDDM
from core.template.field import Field


class ExtractionResult:
    """
    Результат извлечения полей документа по шаблону. Представляет собой словарь значений полей,
    где ключом является название поля, а значением - извлеченное значение или None, если извлечение не удалось.
    """

    def __init__(self):
        self.values: Dict[str, Optional[str]] = {}

    def get(self, field_name: str) -> Optional[str]:
        return self.values.get(field_name)

    def add(self, field_name: str, value: Optional[str]):
        self.values[field_name] = value

    @staticmethod
    def load(path: Path) -> "ExtractionResult":
        with path.open("r", encoding="utf-8") as f:
            values = json.load(f)
            if not isinstance(values, dict):
                raise ValueError(f"Invalid extraction result file: {path}")

            result = ExtractionResult()
            for field_name, value in values.items():
                if not isinstance(field_name, str) or not isinstance(value, str):
                    raise ValueError(f"Invalid field name or value in extraction result file: {path}")
                result.add(field_name, value)
            return result

    def save(self, path: Path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.values, f, indent=2, ensure_ascii=False)


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

            extraction_result = self._extract(document.template, document.uddm)
            extraction_result.save(document.extraction_result_file_path())
            return ModuleResult.OK

        except Exception:
            self.log_exception()
            return ModuleResult.FAILED

    def _extract(self, template: Template, uddm: UDDM) -> ExtractionResult:
        if not template.fields:
            template.fields = template.code.fields()

        result = ExtractionResult()
        for field in template.fields:
            try:
                text = field.selector._select(uddm)
                if not text:
                    self.log(WARNING, f"Error selecting text for field {field.name}")
                    continue

                value = field.extractor._extract(text)
                if value is None:
                    self.log(WARNING, f"Error extracting value for field {field.name}")
                    continue

                result.add(field.name, value)
                self.log(INFO, f"Value for field {field.name} extracted successfully")

            except Exception:
                result.add(field.name, None)
                self.log(WARNING, f"Error extracting field {field.name}", exc_info=True)

        return result
