"""Концепт :Организация — юридическое лицо."""
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
_PRED_NAME: URIRef = _NS["названиеОрганизации"]

# Юридические префиксы, которые отбрасываются при нормализации: они
# меняются от документа к документу для одной и той же организации
# (ФГБОУ ВО → ФГБУН), но identity у организации одно.
_LEGAL_PREFIXES_RE = re.compile(
    r"^(?:фгбоу\s+во|фгбуну?|фгуп|фгуп\s+нии|фгбун|фгаоу\s+во|оаo|оао|зао|пао|ао|ооо|тоо)\s+",
    re.IGNORECASE,
)


class OrganizationConcept(BaseConcept):
    """Концепт ``:Организация`` — юридическое лицо.

    Identity-стратегия:
        * lowercase + удаление кавычек, дефисов-uniside → ASCII-дефис,
          схлопывание пробелов;
        * удаление юридических префиксов (``ФГБОУ ВО``, ``ФГБУН``,
          ``ООО`` и т. п.) — это позволяет «Новосибирский государственный
          университет» и «ФГБОУ ВО Новосибирский государственный
          университет» схлопываться в один индивид.

    В литерал ``:названиеОрганизации`` пишется ИСХОДНОЕ значение
    (``raw.strip()``) — пользователю важно видеть, как было записано
    в документе. У ``:названиеОрганизации`` в схеме ``mergePolicy=Add``,
    поэтому несколько вариаций безболезненно сосуществуют.

    Состав :class:`ConceptParts`:
        canonical: Полностью нормализованная строка для хеширования
            (``"новосибирский государственный университет"``). Это же
            значение, что используется legacy-кодом как ``canonical``.
        parts.name: Исходное значение после ``strip`` — для записи в
            литерал.
    """

    name: ClassVar[str] = "organization"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Организация"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое название организации")

        original = str(raw).strip()
        text = original.replace("ё", "е").replace("Ё", "Е").lower()
        text = re.sub(r"[«»\"']+", "", text)
        text = re.sub(r"[‐-―]", "-", text)  # юникод-тире → ASCII-дефис
        text = re.sub(r"\s+", " ", text).strip()
        text = _LEGAL_PREFIXES_RE.sub("", text).strip()

        if not text:
            raise ConceptError(
                f"После нормализации название организации пустое: {raw!r}"
            )

        return ConceptParts(canonical=text, parts={"name": original})

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        return f"Организация_{short_sha1(parts.canonical)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        # В литерал кладём parts.name (исходную форму), не canonical.
        name_value = parts.get("name") or parts.canonical
        predicate = DraftNode(DraftNode.Type.IRI, _PRED_NAME)
        obj = DraftNode(
            DraftNode.Type.LITERAL,
            Literal(name_value, datatype=XSD.string),
        )
        return (
            DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, predicate, obj),
        )


__all__ = ["OrganizationConcept"]
