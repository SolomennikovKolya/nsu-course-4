from core.document import Document
from core.template.base import *
from core.template.field_extractor import *
from core.template.field_selector import *
from core.template.field_validator import *


class TemplateCode(BaseTemplateCode):

    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        return True

    def fields(self) -> List[Field]:
        raise NotImplementedError()

    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        return ValidationResult()

    def build_triples(self, validation_result: ValidationResult) -> List[Dict]:
        raise NotImplementedError()


"""
Пример:
class TemplateCode(BaseTemplateCode):

    def classify(self, document: Document) -> bool:
        return True

    def fields(self) -> List[Field]:
        return [
            Field(
                name="student_name",
                description="ФИО студента",
                selector=select().paragraph_after("Студент"),
                extractor=extract().regex(r"[А-ЯЁ][а-яё]+ [А-ЯЁ]\.[А-ЯЁ]\."),
                field_type=Field.Type.INDIVIDUAL,
                validator=validate().required()
            ),
            Field(
                name="grade",
                description="Оценка",
                selector=select().table_cell_contains("Оценка").right_cell(),
                extractor=extract().regex(r"[2-5]"),
                field_type=Field.Type.LITERAL,
                validator=validate().required().in_range(2, 5)
            )
        ]

    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        return self._run_validation(extraction_result)

    def build_triples(self, validation_result: ValidationResult) -> List[Dict]:
        triples = []

        name = validation_result.validated.get("student_name")
        grade = validation_result.validated.get("grade")

        if name and grade:
            triples.append({
                "subject": name,
                "predicate": "hasGrade",
                "object": grade
            })

        return triples
"""
