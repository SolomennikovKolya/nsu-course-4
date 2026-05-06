"""
Концепт xsd:date — календарная дата.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import ClassVar, Dict

from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


# Соответствие префикса месяца его номеру. Префикс используется специально,
# чтобы один и тот же ключ ловил все падежи: «январь», «января», «январе»…
_RU_MONTHS: Dict[str, int] = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


class DateConcept(BaseConcept):
    """Концепт ``xsd:date`` — календарная дата.

    Это ``DATATYPE``-концепт: в графе он живёт только как литерал с
    типом ``xsd:date``, индивид с собственным IRI не порождается.
    Триплеты не выдаёт (``build_triples`` дефолтный, возвращает пусто).

    Поддерживаемые формы входа:
        * ISO: ``"2025-05-19"``;
        * с точкой/слешем/тире: ``"12.09.2025"``, ``"29.09.25"``,
          ``"12/09/2025"``, ``"12-09-2025"``;
        * русский с месяцем-словом: ``"20 декабря 2024 г."``,
          ``"«29» сентября 2025 г."``, ``'"29" сентября 2025 г.'`` —
          кавычки и хвост ``"г."`` снимаются перед разбором.

    Двузначный год расширяется до ``20XX``. Регулярки сознательно
    нестрогие к разделителям и пробелам — реальные документы пишут
    даты как угодно.

    Состав :class:`ConceptParts`:
        canonical: ISO-строка ``"YYYY-MM-DD"`` (то, что хранится в
            ``value_normalized`` и пишется в ``Literal(..., XSD.date)``).
        parts.year: Год как 4-значная строка.
        parts.month: Месяц как 2-значная строка с ведущим нулём.
        parts.day: День как 2-значная строка с ведущим нулём.
    """

    name: ClassVar[str] = "date"
    kind: ClassVar[ConceptKind] = ConceptKind.DATATYPE
    onto_class_local: ClassVar[None] = None

    _RE_ISO: ClassVar[re.Pattern] = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
    _RE_DOTTED: ClassVar[re.Pattern] = re.compile(
        r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})"
    )
    _RE_RU_WORD: ClassVar[re.Pattern] = re.compile(
        r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})"
    )

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустая строка даты")

        # Чистка: NBSP/табы → пробелы, схлопывание, удаление кавычек
        # и хвоста "г." / "г".
        text = str(raw).replace(" ", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
        text = re.sub(r"\s+г\.?\s*$", "", text).strip()

        # 1. ISO `YYYY-MM-DD`.
        m = cls._RE_ISO.search(text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return cls._build_parts(y, mo, d, raw)

        # 2. С точкой/слешем/тире `D.M.Y` (двузначный год → +2000).
        m = cls._RE_DOTTED.search(text)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            return cls._build_parts(y, mo, d, raw)

        # 3. Русский «20 декабря 2024».
        m = cls._RE_RU_WORD.search(text)
        if m:
            d = int(m.group(1))
            month_word = m.group(2).lower().replace("ё", "е")
            y = int(m.group(3))
            for prefix, mo in _RU_MONTHS.items():
                if month_word.startswith(prefix):
                    return cls._build_parts(y, mo, d, raw)

        raise ConceptError(f"Не удалось распарсить дату: {raw!r}")

    @classmethod
    def _build_parts(cls, year: int, month: int, day: int, raw: str) -> ConceptParts:
        try:
            dt: date = datetime(year, month, day).date()
        except ValueError as ex:
            raise ConceptError(f"Некорректная дата: {raw!r}") from ex
        iso = dt.isoformat()
        return ConceptParts(
            canonical=iso,
            parts={
                "year": str(dt.year),
                "month": f"{dt.month:02d}",
                "day": f"{dt.day:02d}",
            },
        )


__all__ = ["DateConcept"]
