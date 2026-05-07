"""Концепт :ВКР — выпускная квалификационная работа."""
from __future__ import annotations

import re
from typing import ClassVar, Sequence

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import XSD

from app.settings import SUBJECT_NAMESPACE_IRI
from core.concepts._hash import short_sha1
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


_NS = Namespace(SUBJECT_NAMESPACE_IRI)
_PRED_THESIS_TITLE: URIRef = _NS["темаВКР"]


class ThesisConcept(BaseConcept):
    """Концепт ``:ВКР`` — ВКР, идентифицируемая темой.

    Парсит тему ВКР: lowercase, удаление кавычек, замена юникод-тире на
    ASCII-дефис, схлопывание пробелов, удаление концевой пунктуации.
    IRI = ``ВКР_<sha1[:12](canonical)>``.

    Когда у документа НЕТ поля с темой, IRI ВКР строит сам
    :class:`TemplateGraphBuilder` от IRI студента — это уже
    builder-уровень и в концепт не входит.

    Состав :class:`ConceptParts`:
        canonical: Тема в нижнем регистре без пунктуации (для хеша).
        parts.title: Исходный заголовок (``raw.strip()``) — пишется в
            литерал ``:темаВКР``.
    """

    name: ClassVar[str] = "thesis"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "ВКР"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустая тема ВКР")
        original = str(raw).strip()
        text = original.replace("ё", "е").replace("Ё", "Е").lower()
        text = re.sub(r"[«»\"']+", "", text)
        text = re.sub(r"[‐-―]", "-", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*[.!?]+\s*$", "", text)
        if not text:
            raise ConceptError(f"После нормализации тема ВКР пустая: {raw!r}")
        return ConceptParts(canonical=text, parts={"title": original})

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
        title_value = parts.get("title") or parts.canonical
        predicate = DraftNode(DraftNode.Type.IRI, _PRED_THESIS_TITLE)
        obj = DraftNode(
            DraftNode.Type.LITERAL,
            Literal(title_value, datatype=XSD.string),
        )
        return (
            DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, predicate, obj),
        )


__all__ = ["ThesisConcept"]
