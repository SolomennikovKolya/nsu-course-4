"""Концепт :УченоеЗвание — учёное звание (перечисление)."""
from __future__ import annotations

from typing import ClassVar, List, Tuple

from core.concepts._enum import match_enum
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


_SYNONYMS: List[Tuple[str, str]] = [
    ("член-корреспондент ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("чл.-корр. ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("чл-корр ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("академик ран", "УченоеЗвание_АкадемикРАН"),
    ("академик риа", "УченоеЗвание_АкадемикРИА"),
    ("профессор", "УченоеЗвание_Профессор"),
    ("доцент", "УченоеЗвание_Доцент"),
]


class TitleConcept(BaseConcept):
    """Концепт ``:УченоеЗвание`` — учёное звание (перечисление)."""

    name: ClassVar[str] = "academic_title"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "УченоеЗвание"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение учёного звания")
        local = match_enum(str(raw), _SYNONYMS)
        if not local:
            raise ConceptError(f"Не удалось сопоставить учёное звание: {raw!r}")
        return ConceptParts(canonical=local)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return parts.canonical


__all__ = ["TitleConcept"]
