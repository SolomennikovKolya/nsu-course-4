from typing import List

from core import *


class TemplateCode(BaseTemplateCode):

    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        return False

    def fields(self) -> List[Field]:
        raise NotImplementedError()

    def build(self, b: TemplateGraphBuilder):
        raise NotImplementedError()
