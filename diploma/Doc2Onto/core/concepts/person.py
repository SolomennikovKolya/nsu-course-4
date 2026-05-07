"""
Концепт :Персона — физическое лицо.
"""
from __future__ import annotations

import re
from typing import ClassVar, Optional, Sequence

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import XSD

from app.settings import SUBJECT_NAMESPACE_IRI
from core.concepts._hash import short_sha1
from core.concepts._morph import detect_gender, to_nominative
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.graph.draft_graph import DraftNode, DraftTriple


_NS = Namespace(SUBJECT_NAMESPACE_IRI)
_PRED_FIO: URIRef = _NS["фио"]
_PRED_LAST: URIRef = _NS["фамилия"]
_PRED_FIRST: URIRef = _NS["имя"]
_PRED_MIDDLE: URIRef = _NS["отчество"]


class PersonConcept(BaseConcept):
    """Концепт ``:Персона`` — физическое лицо.

    Парсит ФИО в произвольном падеже («направить **Соломенникову Николаю
    Александровичу**») и приводит каждую часть к именительному падежу
    через :mod:`core.concepts._morph` (pymorphy3). Это критично: без
    морфологии один и тот же человек в разных документах получал бы
    разный IRI и не схлопывался в графе.

    Стратегия идентичности (IRI):
        * рассчитываем «sort key» — ``lower(фамилия)|инициал_имени|инициал_отчества``
          в нижнем регистре и без точек, всегда из НОРМАЛИЗОВАННЫХ
          (именительных) частей;
        * IRI = ``Персона_<sha1[:12](sort_key)>``.

    Sort-key намеренно не содержит полное имя — иначе «Иванов Иван И.» и
    «Иванов Иван Иванович» получили бы разные IRI, хотя речь об одном
    человеке. Сейчас они схлопываются по первым буквам.

    Состав :class:`ConceptParts`:
        canonical: Полное ФИО в именительном падеже,
            ``"Соломенников Николай Александрович"`` — это то, что
            хранится в ``value_normalized`` и пишется в литерал ``:фио``.
        parts.last_name: Фамилия в именительном (с восстановлением
            регистра первой буквы).
        parts.first_name: Имя или инициал в именительном.
        parts.middle_name: Отчество в именительном; ``None``, если
            отчество не указано.
        parts.sort_key: Внутренний ключ для хеширования IRI, см. выше.
    """

    name: ClassVar[str] = "person"
    kind: ClassVar[ConceptKind] = ConceptKind.CLASS_INDIVIDUAL
    onto_class_local: ClassVar[str] = "Персона"

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустое ФИО")

        # Базовая чистка как в legacy ValueTransformer._clean_text:
        # ё→е (без этого pymorphy ломается на «Соловьёв»), NBSP/табы → пробел.
        text = str(raw).replace("ё", "е").replace("Ё", "Е")
        text = text.replace(" ", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()

        # Разбиение по пробелам и точкам — точки нужны, чтобы «Иванов И. И.»
        # давало три токена, а не один склеенный.
        tokens = [p for p in re.split(r"[\s.]+", text) if p]
        if len(tokens) < 2:
            raise ConceptError(
                f"ФИО должно содержать как минимум фамилию и имя/инициал: {raw!r}"
            )

        last_raw = tokens[0]
        first_raw = tokens[1]
        middle_raw: Optional[str] = tokens[2] if len(tokens) > 2 else None

        # Пол сначала пробуем по имени, потом по отчеству — отчество
        # надёжнее (по суффиксу), но обычно идёт последним.
        gender = detect_gender(first_raw) or (
            detect_gender(middle_raw) if middle_raw else None
        )

        last_norm = to_nominative(last_raw, kind="surname", gender=gender)
        first_norm = to_nominative(first_raw, kind="first", gender=gender)
        middle_norm: Optional[str] = (
            to_nominative(middle_raw, kind="patronymic", gender=gender)
            if middle_raw
            else None
        )

        # Sort key: lower(фамилия)|инициал_имени|инициал_отчества, без точек.
        last_key = last_norm.lower().replace(".", "").strip()
        first_init = cls._first_letter(first_norm)
        middle_init = cls._first_letter(middle_norm) if middle_norm else ""

        if not last_key or not first_init:
            raise ConceptError(
                f"Не удалось извлечь фамилию и инициал имени: {raw!r}"
            )

        sort_key = f"{last_key}|{first_init}|{middle_init}"

        # canonical = полное ФИО в именительном.
        full_parts = [last_norm, first_norm]
        if middle_norm:
            full_parts.append(middle_norm)
        full_name = " ".join(full_parts)

        return ConceptParts(
            canonical=full_name,
            parts={
                "last_name": last_norm,
                "first_name": first_norm,
                "middle_name": middle_norm,
                "sort_key": sort_key,
            },
        )

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        sort_key = parts.get("sort_key")
        if not sort_key:
            # Если parts получены не из parse() — пересчитаем
            # из canonical, чтобы IRI оставался стабильным.
            sort_key = cls.parse(parts.canonical).get("sort_key") or ""
        return f"Персона_{short_sha1(sort_key)}"

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject: DraftNode,
    ) -> Sequence[DraftTriple]:
        triples = []
        # Литералы выдаём только для непустых частей: для большинства
        # людей в документах вуза отчество есть, но иногда его нет (или
        # указан только инициал — тогда в parts.middle_name тоже строка).
        pairs = [
            (_PRED_FIO, parts.canonical),
            (_PRED_LAST, parts.get("last_name")),
            (_PRED_FIRST, parts.get("first_name")),
            (_PRED_MIDDLE, parts.get("middle_name")),
        ]
        for predicate, value in pairs:
            if not value or not str(value).strip():
                continue
            pred_node = DraftNode(DraftNode.Type.IRI, predicate)
            obj_node = DraftNode(
                DraftNode.Type.LITERAL,
                Literal(str(value), datatype=XSD.string),
            )
            triples.append(
                DraftTriple(DraftTriple.Type.DATA_PROPERTY, subject, pred_node, obj_node)
            )
        return tuple(triples)

    # ---------- helpers ----------

    @staticmethod
    def _first_letter(word: Optional[str]) -> str:
        if not word:
            return ""
        normalized = word.lower().replace(".", "").strip()
        return normalized[0] if normalized else ""


__all__ = ["PersonConcept"]
