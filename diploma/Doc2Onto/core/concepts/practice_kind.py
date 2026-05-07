"""Концепт :ВидПрактики (перечисление)."""
from __future__ import annotations

from typing import ClassVar, List, Tuple

from core.concepts._enum import match_enum
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


_SYNONYMS: List[Tuple[str, str]] = [
    ("научно-исследовательская работа", "ВидПрактики_НИР"),
    ("нир", "ВидПрактики_НИР"),
    ("преддипломная практика", "ВидПрактики_Преддипломная"),
    ("преддипломная", "ВидПрактики_Преддипломная"),
    ("эксплуатационная практика", "ВидПрактики_Эксплуатационная"),
    ("эксплуатационная", "ВидПрактики_Эксплуатационная"),
    ("производственная практика", "ВидПрактики_Производственная"),
    ("производственная", "ВидПрактики_Производственная"),
    ("учебная практика", "ВидПрактики_Учебная"),
    ("учебная", "ВидПрактики_Учебная"),
]


class PracticeKindConcept(BaseConcept):
    """Концепт ``:ВидПрактики`` — вид практики (перечисление)."""

    name: ClassVar[str] = "practice_kind"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "ВидПрактики"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение вида практики")
        local = match_enum(str(raw), _SYNONYMS)
        if not local:
            raise ConceptError(f"Не удалось сопоставить вид практики: {raw!r}")
        return ConceptParts(canonical=local)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return parts.canonical


__all__ = ["PracticeKindConcept"]
