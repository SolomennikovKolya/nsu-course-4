"""Концепт ``email`` — литерал электронной почты."""
from __future__ import annotations

from typing import ClassVar

from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


class EmailConcept(BaseConcept):
    """Концепт ``email`` — литерал email-адреса.

    Identity-стратегия: нет (DATATYPE — собственного индивида не имеет).
    Канонизация: lowercase. Проверяет наличие ровно одной ``@`` с
    непустыми ``local`` и ``domain`` частями.

    Состав :class:`ConceptParts`:
        canonical: ``"local@domain"`` в нижнем регистре. Это значение
            пишется в литерал ``:email`` у родительского индивида.
        parts.local: Часть до ``@`` (исходный регистр).
        parts.domain: Часть после ``@`` (исходный регистр).
    """

    name: ClassVar[str] = "email"
    kind: ClassVar[ConceptKind] = ConceptKind.DATATYPE
    onto_class_local: ClassVar[None] = None

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустой email")
        text = str(raw).strip()
        parts = text.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ConceptError(
                f"Email должен содержать ровно одну '@' и непустые части: {raw!r}"
            )
        local, domain = parts
        canonical = f"{local}@{domain}".lower()
        return ConceptParts(
            canonical=canonical,
            parts={"local": local, "domain": domain},
        )


__all__ = ["EmailConcept"]
