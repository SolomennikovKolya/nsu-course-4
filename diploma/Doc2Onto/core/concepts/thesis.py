"""Концепт :ВКР — выпускная квалификационная работа."""
from __future__ import annotations

from typing import ClassVar, Sequence

from core.concepts._hash import short_sha1
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


class ThesisConcept(BaseConcept):
    """Концепт ``:ВКР`` — выпускная квалификационная работа.

    Identity-стратегия: одна ВКР на студента. IRI = хеш от локального
    имени IRI студента. Тема ВКР — это литерал ``:темаВКР``, не часть
    identity; смена формулировки темы обновляет литерал, не порождая
    нового индивида.

    Использование:
        * **Сама по себе строка-тема** не описывает ВКР — нужен IRI
          студента. Поэтому метод :meth:`parse` принимает каноническую
          форму ``"<person_iri_local>"`` (для контракта
          :class:`BaseConcept` и идемпотентности), а основной путь —
          :meth:`from_student` из :class:`TemplateGraphBuilder`.
        * **Идентифицирующих литералов в графе у ВКР нет.**
          Тема и связь со студентом (``:авторВКР``) ставятся отдельно
          builder-ом после создания индивида.

    Состав :class:`ConceptParts`:
        canonical: Локальное имя IRI студента (``"Персона_a1b2c3..."``).
            Используется для хеширования IRI ВКР.
        parts.person: То же значение (для единообразия с другими
            composite-концептами).
    """

    name: ClassVar[str] = "thesis"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "ВКР"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        """Принимает локальное имя IRI студента (``"Персона_..."``).

        Формально нужен для контракта :class:`BaseConcept` и
        идемпотентности. На практике builder использует
        :meth:`from_student`.
        """
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустой IRI студента для ВКР")
        return cls.from_student(str(raw).strip())

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return f"ВКР_{short_sha1(parts.canonical)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        # Тема и связь :авторВКР ставит builder.
        return ()

    @classmethod
    def from_student(cls, student_iri_local: str) -> ConceptParts:
        """Собрать :class:`ConceptParts` из локального имени IRI студента.

        Args:
            student_iri_local: ``"Персона_a1b2c3d4e5f6"``.

        Raises:
            ConceptError: если имя пустое.
        """
        person = (student_iri_local or "").strip()
        if not person:
            raise ConceptError("Пустой IRI студента для ВКР")
        return ConceptParts(canonical=person, parts={"person": person})


__all__ = ["ThesisConcept"]
