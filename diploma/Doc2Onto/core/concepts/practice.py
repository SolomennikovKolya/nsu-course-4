"""Концепт :Практика — практика студента."""
from __future__ import annotations

from typing import ClassVar, Sequence

from core.concepts._hash import short_sha1
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


class PracticeConcept(BaseConcept):
    """Концепт ``:Практика``.

    Identity-стратегия — *составная*: индивид Практики идентифицируется
    парой ``(person_iri_local, start_date_iso)``. Дата начала — стабильный
    естественный идентификатор: две практики одного студента не могут
    начинаться в один день. IRI вычисляется как
    ``Практика_<sha1[:12]>(person_lower | start_date)``.

    Особенности концепта:
        * **Сама по себе строка с одним-единственным значением** не
          описывает практику: концепту нужны две части. Поэтому метод
          :meth:`parse` принимает либо каноническую строку формата
          ``"person|start_date"`` (для соответствия контракту
          :class:`BaseConcept` и идемпотентности), либо
          :meth:`from_components` принимает части напрямую — это основной
          путь использования из :class:`TemplateGraphBuilder`.
        * **Идентифицирующих литералов в графе у Практики нет.**
          Связи (``:практикантВПрактике``, литералы ``:видПрактики``,
          ``:датаНачалаПрактики`` и т. п.) ставит сам builder *после*
          создания индивида — у концепта нет доступа к node'ам student,
          только к их каноническим строкам, поэтому
          :meth:`build_triples` — пустой кортеж.

    Состав :class:`ConceptParts`:
        canonical: ``"<person>|<start_date>"`` в нижнем регистре.
            Используется для хеширования IRI.
        parts.person: Локальное имя IRI студента (``Персона_a1b2c3...``).
        parts.start_date: Дата начала практики в ISO-формате
            (``"2024-09-01"``).
    """

    name: ClassVar[str] = "practice"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Практика"

    # ------------------------------------------------------------------
    # Контрактные методы (BaseConcept)
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        """Разобрать pipe-разделённую строку формата ``"person|start_date"``.

        Формально нужен для соответствия контракту :class:`BaseConcept`
        и идемпотентности (``parse(parse(x).canonical)``). На практике
        builder вызывает :meth:`from_components` напрямую.
        """
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое значение практики")
        parts = str(raw).split("|")
        if len(parts) != 2:
            raise ConceptError(
                f"Ожидался формат 'person|start_date', получено: {raw!r}"
            )
        person, start_date = (p.strip() for p in parts)
        return cls.from_components(person, start_date)

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return f"Практика_{short_sha1(parts.canonical)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        # Identifying-связи (студент, дата начала) ставит builder — у
        # концепта нет доступа к node student, только к его локальному
        # имени IRI.
        return ()

    # ------------------------------------------------------------------
    # Удобный конструктор для builder-а
    # ------------------------------------------------------------------

    @classmethod
    def from_components(
        cls,
        person_iri_local: str,
        start_date: str,
    ) -> ConceptParts:
        """Собрать :class:`ConceptParts` из двух компонентов идентичности.

        Args:
            person_iri_local: Локальное имя IRI студента (например
                ``"Персона_a1b2c3d4e5f6"``).
            start_date: Дата начала практики в ISO-формате
                (``"2024-09-01"``).

        Raises:
            ConceptError: если хотя бы один компонент пуст.
        """
        person = (person_iri_local or "").strip()
        date_s = (start_date or "").strip()
        if not person or not date_s:
            raise ConceptError("person/start_date не должны быть пустыми")
        canonical = f"{person.lower()}|{date_s.lower()}"
        return ConceptParts(
            canonical=canonical,
            parts={"person": person, "start_date": date_s},
        )


__all__ = ["PracticeConcept"]
