from typing import List, Dict

from core.template.base import BaseTemplateCode
from core.template.field import Field
from core.template.field_selector import *
from core.template.field_extractor import *
from core.template.field_validator import *
from core.uddm.model import *


class TemplateCode(BaseTemplateCode):

    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        return False

    def fields(self) -> List[Field]:
        raise NotImplementedError()

    def build_triples(self, fields_values: Dict[str, str]) -> List[Dict]:
        raise NotImplementedError()
