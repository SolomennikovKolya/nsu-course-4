"""Концепт :НаправлениеПодготовки — направление подготовки."""
from __future__ import annotations

import re
from typing import ClassVar, Sequence

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import XSD

from app.settings import SUBJECT_NAMESPACE_IRI
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


_NS = Namespace(SUBJECT_NAMESPACE_IRI)
_PRED_CODE: URIRef = _NS["кодНаправления"]


class DirectionConcept(BaseConcept):
    """Концепт ``:НаправлениеПодготовки``.

    Идентифицируется кодом формата ``XX.XX.XX`` (например ``09.03.04``).
    IRI стабилен и читаем: ``Направление_09_03_04`` (без хеша). В графе
    представляется индивидом с одним литералом ``:кодНаправления``.

    Название направления (``"Программная инженерия"``) хранится в
    отдельном поле документа и кладётся в граф через
    ``:названиеНаправления`` отдельно — это не часть identity, поэтому
    в концепт оно не входит.

    Состав :class:`ConceptParts`:
        canonical: Код в каноничной форме ``"09.03.04"``.
        parts.code: То же значение.
    """

    name: ClassVar[str] = "direction"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "НаправлениеПодготовки"

    _RE_CODE: ClassVar[re.Pattern] = re.compile(r"\d{2}\.\d{2}\.\d{2}")

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустой код направления подготовки")
        text = str(raw).replace("ё", "е").replace("Ё", "Е")
        text = re.sub(r"\s+", " ", text).strip()
        m = cls._RE_CODE.search(text)
        if not m:
            raise ConceptError(
                f"Не удалось извлечь код направления вида XX.XX.XX: {raw!r}"
            )
        code = m.group(0)
        return ConceptParts(canonical=code, parts={"code": code})

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        # Стабильный IRI без хеша: точки → подчёркивания.
        return f"Направление_{parts.canonical.replace('.', '_')}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        predicate = DraftNode(DraftNode.Type.IRI, _PRED_CODE)
        obj = DraftNode(
            DraftNode.Type.LITERAL,
            Literal(parts.canonical, datatype=XSD.string),
        )
        return (
            DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, predicate, obj),
        )


__all__ = ["DirectionConcept"]
