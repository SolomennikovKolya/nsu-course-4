"""Концепт :Профиль — профиль (направленность) подготовки."""
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
_PRED_NAME: URIRef = _NS["названиеПрофиля"]


class ProfileConcept(BaseConcept):
    """Концепт ``:Профиль``.

    Идентифицируется sha1[:12] от lowercase-нормализованного названия.
    Так «Программная инженерия» и «программная инженерия» в разных
    документах схлапываются в один индивид.

    Состав :class:`ConceptParts`:
        canonical: Имя профиля в нижнем регистре, без двойных пробелов.
            Это значение пишется в литерал ``:названиеПрофиля`` И идёт в
            хеш. Регистр пользовательского ввода теряется — это
            компромисс ради schлопывания.
        parts.name: То же, что canonical (для единообразия с другими концептами).
    """

    name: ClassVar[str] = "profile"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Профиль"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое название профиля")
        text = str(raw).replace("ё", "е").replace("Ё", "Е").lower()
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            raise ConceptError(f"После нормализации название профиля пустое: {raw!r}")
        return ConceptParts(canonical=text, parts={"name": text})

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return f"Профиль_{short_sha1(parts.canonical)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject_iri: URIRef,
    ) -> Sequence[DraftTriple]:
        subject = DraftNode(DraftNode.Type.IRI, subject_iri)
        predicate = DraftNode(DraftNode.Type.IRI, _PRED_NAME)
        obj = DraftNode(
            DraftNode.Type.LITERAL,
            Literal(parts.canonical, datatype=XSD.string),
        )
        return (
            DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, predicate, obj),
        )


__all__ = ["ProfileConcept"]
