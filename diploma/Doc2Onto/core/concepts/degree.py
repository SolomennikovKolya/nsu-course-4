"""Концепт :УченаяСтепень — учёная степень (перечисление)."""
from __future__ import annotations

from typing import ClassVar, List, Tuple

from core.concepts._enum import match_enum
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


_SYNONYMS: List[Tuple[str, str]] = [
    ("кандидат физико-математических наук", "УченаяСтепень_КандидатФизМатНаук"),
    ("к.ф.-м.н.", "УченаяСтепень_КандидатФизМатНаук"),
    ("кфмн", "УченаяСтепень_КандидатФизМатНаук"),
    ("доктор физико-математических наук", "УченаяСтепень_ДокторФизМатНаук"),
    ("д.ф.-м.н.", "УченаяСтепень_ДокторФизМатНаук"),
    ("дфмн", "УченаяСтепень_ДокторФизМатНаук"),
    ("кандидат технических наук", "УченаяСтепень_КандидатТехнНаук"),
    ("к.т.н.", "УченаяСтепень_КандидатТехнНаук"),
    ("ктн", "УченаяСтепень_КандидатТехнНаук"),
    ("доктор технических наук", "УченаяСтепень_ДокторТехнНаук"),
    ("д.т.н.", "УченаяСтепень_ДокторТехнНаук"),
    ("дтн", "УченаяСтепень_ДокторТехнНаук"),
    ("кандидат педагогических наук", "УченаяСтепень_КандидатПедНаук"),
    ("к.п.н.", "УченаяСтепень_КандидатПедНаук"),
    ("доктор педагогических наук", "УченаяСтепень_ДокторПедНаук"),
    ("д.п.н.", "УченаяСтепень_ДокторПедНаук"),
]


class DegreeConcept(BaseConcept):
    """Концепт ``:УченаяСтепень`` — учёная степень (перечисление)."""

    name: ClassVar[str] = "degree"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "УченаяСтепень"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение учёной степени")
        local = match_enum(str(raw), _SYNONYMS)
        if not local:
            raise ConceptError(f"Не удалось сопоставить учёную степень: {raw!r}")
        return ConceptParts(canonical=local)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return parts.canonical


__all__ = ["DegreeConcept"]
