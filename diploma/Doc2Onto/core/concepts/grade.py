"""Концепт :Оценка — итоговая оценка (перечисление)."""
from __future__ import annotations

from typing import ClassVar, List, Tuple

from core.concepts._enum import match_enum
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


_SYNONYMS: List[Tuple[str, str]] = [
    ("отлично", "Оценка_Отлично"),
    ("хорошо", "Оценка_Хорошо"),
    ("удовлетворительно", "Оценка_Удовлетворительно"),
    ("неудовлетворительно", "Оценка_Неудовлетворительно"),
    ("неуд", "Оценка_Неудовлетворительно"),
    ("отл", "Оценка_Отлично"),
    ("хор", "Оценка_Хорошо"),
    ("удовл", "Оценка_Удовлетворительно"),
    ("5", "Оценка_Отлично"),
    ("4", "Оценка_Хорошо"),
    ("3", "Оценка_Удовлетворительно"),
    ("2", "Оценка_Неудовлетворительно"),
]


class GradeConcept(BaseConcept):
    """Концепт ``:Оценка`` — итоговая оценка (перечисление)."""

    name: ClassVar[str] = "grade"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Оценка"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение оценки")
        local = match_enum(str(raw), _SYNONYMS)
        if not local:
            raise ConceptError(f"Не удалось сопоставить оценку: {raw!r}")
        return ConceptParts(canonical=local)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return parts.canonical


__all__ = ["GradeConcept"]
