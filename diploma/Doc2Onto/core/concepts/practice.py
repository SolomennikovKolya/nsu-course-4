"""Концепт :Практика — практика студента."""
from __future__ import annotations

from typing import ClassVar, Sequence

from rdflib import URIRef

from core.concepts._hash import short_sha1
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftTriple


class PracticeConcept(BaseConcept):
    """Концепт ``:Практика``.

    Identity-стратегия — *составная*: индивид Практики идентифицируется
    тройкой ``(person_iri_local, kind_local, year)``. Это значит, что
    студент Иванов, проходящий Учебную практику в 2024/2025 уч.году, —
    это один и тот же индивид, в каких бы документах ни упоминалась
    практика. Чтобы IRI был детерминированным, тройка собирается в
    pipe-разделённую каноническую строку, и от неё берётся ``sha1[:12]``.

    Особенности концепта:
        * **Сама по себе строка с одним-единственным значением** не
          описывает практику: концепту нужны три части. Поэтому метод
          :meth:`parse` принимает либо каноническую строку формата
          ``"person|kind|year"`` (для соответствия контракту
          :class:`BaseConcept`), либо :meth:`from_components` принимает
          три части напрямую — это основной путь использования из
          :class:`TemplateGraphBuilder`.
        * **Идентифицирующих литералов в графе у Практики нет.**
          Связи (``:практикантВПрактике``, ``:видПрактики``,
          ``:учебныйГодПрактики``) ставит сам builder *после* создания
          индивида — у концепта нет доступа к нодам student/kind, только
          к их каноническим строкам, поэтому :meth:`build_triples` —
          пустой кортеж (как у любых индивидов, чья identity сводится
          к одному IRI).

    Состав :class:`ConceptParts`:
        canonical: ``"<person>|<kind>|<year>"`` в нижнем регистре.
            Используется для хеширования IRI.
        parts.person: Локальное имя IRI студента (``Персона_a1b2c3...``).
        parts.kind: Локальное имя индивида ВидПрактики
            (``ВидПрактики_Учебная``).
        parts.year: Учебный год в исходной форме (``"2024/2025"``).
    """

    name: ClassVar[str] = "practice"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Практика"

    # ------------------------------------------------------------------
    # Контрактные методы (BaseConcept)
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        """Разобрать pipe-разделённую строку формата ``"person|kind|year"``.

        Формально нужен для соответствия контракту :class:`BaseConcept`
        и идемпотентности (``parse(parse(x).canonical)``). На практике
        builder вызывает :meth:`from_components` напрямую.
        """
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение практики")
        parts = str(raw).split("|")
        if len(parts) != 3:
            raise ConceptError(
                f"Ожидался формат 'person|kind|year', получено: {raw!r}"
            )
        person, kind_local, year = (p.strip() for p in parts)
        return cls.from_components(person, kind_local, year)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return f"Практика_{short_sha1(parts.canonical)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject_iri: URIRef,
    ) -> Sequence[DraftTriple]:
        # Identifying-связи (студент, вид, год) ставит builder — у
        # концепта нет доступа к node'ам student/kind, только к их
        # каноническим строкам.
        return ()

    # ------------------------------------------------------------------
    # Удобный конструктор для builder-а
    # ------------------------------------------------------------------

    @classmethod
    def from_components(
        cls,
        person_iri_local: str,
        kind_local: str,
        year: str,
    ) -> ConceptParts:
        """Собрать :class:`ConceptParts` из трёх компонентов идентичности.

        Args:
            person_iri_local: Локальное имя IRI студента (например
                ``"Персона_a1b2c3d4e5f6"``).
            kind_local: Локальное имя индивида ВидПрактики (например
                ``"ВидПрактики_Учебная"``).
            year: Учебный год (например ``"2024/2025"``).

        Raises:
            ConceptError: если хотя бы один компонент пуст.
        """
        person = (person_iri_local or "").strip()
        kind_l = (kind_local or "").strip()
        year_s = (year or "").strip()
        if not person or not kind_l or not year_s:
            raise ConceptError(
                "person/kind/year не должны быть пустыми"
            )
        canonical = f"{person.lower()}|{kind_l.lower()}|{year_s.lower()}"
        return ConceptParts(
            canonical=canonical,
            parts={"person": person, "kind": kind_l, "year": year_s},
        )


__all__ = ["PracticeConcept"]
