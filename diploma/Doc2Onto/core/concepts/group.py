"""
Концепт :Группа — учебная группа.
"""
from __future__ import annotations

import re
from typing import ClassVar, Sequence

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import XSD

from app.settings import SUBJECT_NAMESPACE_IRI
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


_NS = Namespace(SUBJECT_NAMESPACE_IRI)
_PRED_NUMBER: URIRef = _NS["номерГруппы"]


class GroupConcept(BaseConcept):
    """Концепт ``:Группа`` — учебная группа.

    Парсит строку с номером учебной группы и порождает стабильный IRI
    вида ``:Группа_<номер>`` (без хеширования: номер сам по себе
    однозначно идентифицирует группу в рамках университета).

    Поддерживаемые формы входа:
        * чисто числовые номера: ``"22204"``, ``"22204а"``;
        * номер, окружённый шумом: ``"группа № 22204"``, ``"гр. 22204"``;
        * буквенно-цифровые без длинных чисел в составе: ``"А-12"``,
          ``"М-1"``.

    Стратегия разбора — приоритет у длинного числа (``\\d{3,}``) с
    возможным буквенным суффиксом, чтобы отсечь шум вроде ``"№ 1"`` или
    ``"курс 4"``. Если длинного числа нет — пробуем буквенно-цифровое
    обозначение, затем любое число как fallback. Поведение совпадает с
    устаревшим ``ValueTransformer.group``: для входа ``"М-2024-1"``
    возвращается ``"2024"`` (длинное число выигрывает у общего
    обозначения). Менять это нельзя без миграции уже сохранённых графов.

    Состав :class:`ConceptParts`:
        canonical: Извлечённый номер (``"22204"``, ``"М-2024-1"``).
            Это же значение пишется в литерал ``:номерГруппы`` и в
            суффикс IRI.
        parts.number: Тот же номер. Дублируется для единообразия с
            другими концептами, у которых ``canonical`` может
            отличаться от извлечённой части (например, у Person
            canonical — внутренний ключ, не совпадающий с самим ФИО).
    """

    name: ClassVar[str] = "group"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Группа"

    _RE_LONG_NUMBER: ClassVar[re.Pattern] = re.compile(r"\d{3,}[A-Za-zА-Яа-я]*")
    _RE_ALPHANUM: ClassVar[re.Pattern] = re.compile(r"[A-Za-zА-Яа-я]+[-_]?\d+")
    _RE_FALLBACK: ClassVar[re.Pattern] = re.compile(r"\d+")

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустой номер группы")

        text = str(raw).replace(" ", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()

        for pattern in (cls._RE_LONG_NUMBER, cls._RE_ALPHANUM, cls._RE_FALLBACK):
            m = pattern.search(text)
            if m is not None:
                token = m.group(0)
                return ConceptParts(canonical=token, parts={"number": token})

        raise ConceptError(f"Не удалось разобрать номер группы: {raw!r}")

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        # Стабильный IRI без хеша: номер группы уникален сам по себе.
        return f"Группа_{parts.canonical}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        predicate = DraftNode(DraftNode.Type.IRI, _PRED_NUMBER)
        obj = DraftNode(DraftNode.Type.LITERAL, Literal(parts.canonical, datatype=XSD.string))
        return (
            DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, predicate, obj),
        )


__all__ = ["GroupConcept"]
