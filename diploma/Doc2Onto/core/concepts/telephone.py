"""Концепт ``telephone`` — литерал номера телефона."""
from __future__ import annotations

import re
from typing import ClassVar

from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts


class TelephoneConcept(BaseConcept):
    """Концепт ``telephone`` — литерал номера телефона.

    Принимает ``+7 999 ...``, ``8 999 ...``, ``7 999 ...`` и любые
    разделители (пробелы, дефисы, скобки). Все нецифры выкидываются;
    если осталось 11 цифр и первая — ``7`` или ``8``, отбрасываем код
    страны. Канонический вид — ``+7XXXXXXXXXX`` (10 цифр после ``+7``).

    Identity-стратегия: нет (DATATYPE — собственного индивида не имеет;
    в граф попадает как литерал ``:телефон`` у родительского индивида).

    Состав :class:`ConceptParts`:
        canonical: ``"+7XXXXXXXXXX"``.
    """

    name: ClassVar[str] = "telephone"
    kind: ClassVar[ConceptKind] = ConceptKind.DATATYPE
    onto_class_local: ClassVar[None] = None

    @classmethod
    def parse(cls, raw: str) -> ConceptParts:
        if raw is None or not str(raw).strip():
            raise ConceptError("Пустой номер телефона")
        digits = re.sub(r"\D", "", str(raw))
        if len(digits) == 11 and digits.startswith(("7", "8")):
            digits = digits[1:]
        if len(digits) != 10:
            raise ConceptError(f"Не удалось нормализовать номер: {raw!r}")
        canonical = "+7" + digits
        return ConceptParts(canonical=canonical)


__all__ = ["TelephoneConcept"]
