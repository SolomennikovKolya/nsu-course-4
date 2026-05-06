"""
Морфологические утилиты для приведения частей ФИО к именительному падежу.

Используются :class:`PersonConcept` (и ничем больше). Pymorphy3 загружается
при импорте — это тяжёлая операция (~150 МБ словарей в RAM), поэтому
модуль выделен отдельно: его импорт можно пропустить, если код не работает
с ФИО (например, юнит-тесты GroupConcept или DateConcept).

В документах часто встречается родительный/винительный/дательный падеж
(«направить Соломенникову Николаю Александровичу»), и без морфологической
нормализации хеш ФИО получается разным для одного и того же человека
в разных документах — индивиды не схлапываются в графе.
"""
from typing import Dict, Optional

import pymorphy3


_morph = pymorphy3.MorphAnalyzer()

# Тег pymorphy3 для каждой части ФИО. Используется для отсечения «случайных»
# разборов слова (например, «Соломенников» pymorphy без тега Surn читает
# как мн. ч. от «соломенник» и без фильтра дал бы «Соломенники»).
_PART_TAG: Dict[str, str] = {
    "surname": "Surn",
    "first": "Name",
    "patronymic": "Patr",
}


def detect_gender(first_name: str) -> Optional[str]:
    """Пол по имени: ``"masc"`` / ``"femn"`` / ``None``.

    Имена-инициалы (≤ 2 символа после удаления точек) пол не определяют —
    pymorphy на одной букве выдаёт хаотичные разборы.
    """
    if not first_name:
        return None
    cleaned = first_name.strip()
    if len(cleaned.replace(".", "")) <= 2:
        return None
    for parsed in _morph.parse(cleaned):
        if "Name" in parsed.tag:
            tag = parsed.tag
            if "masc" in tag:
                return "masc"
            if "femn" in tag:
                return "femn"
    return None


def to_nominative(word: str, *, kind: str, gender: Optional[str] = None) -> str:
    """Привести часть ФИО к именительному падежу.

    Args:
        word: Часть ФИО (фамилия, имя или отчество).
        kind: Тип части: ``"surname"`` | ``"first"`` | ``"patronymic"``.
            Используется для выбора подходящего pymorphy-тега и отсечения
            «не-ФИО» разборов.
        gender: Известный пол персоны (``"masc"`` / ``"femn"``); если задан,
            предпочитаются разборы с совпадающим полом. Это снимает омонимию
            «Соломенникова Николая» (мужской gent) ↔ «Соломенникова Мария»
            (женский nomn).

    Стратегия:
      * слово 1–2 символа (инициал) и пустые — оставляем как есть;
      * фамилии через дефис нормализуем покомпонентно;
      * среди разборов pymorphy берём только те, у которых стоит подходящий
        тег части ФИО (``Surn`` / ``Name`` / ``Patr``); если таких нет —
        возвращаем без изменений (любая «коррекция» опасна);
      * среди типизированных предпочитаем совпадающий пол → sing > plur →
        nomn > не-nomn; при необходимости вызываем
        :func:`pymorphy3.Parse.inflect` к ``{"nomn"}``.
    """
    if not word:
        return word

    cleaned = word.strip()
    if not cleaned:
        return word

    if "-" in cleaned and not cleaned.endswith("-"):
        return "-".join(
            to_nominative(p, kind=kind, gender=gender) for p in cleaned.split("-")
        )

    if len(cleaned.replace(".", "")) <= 2:
        return cleaned

    target_tag = _PART_TAG.get(kind)
    if target_tag is None:
        return cleaned

    parses = _morph.parse(cleaned)
    typed = [p for p in parses if target_tag in p.tag]
    if not typed:
        return cleaned

    def _gender_score(p) -> int:
        if gender is None:
            return 0
        if gender in p.tag:
            return 0
        return 2 if (("masc" in p.tag) or ("femn" in p.tag)) else 1

    typed.sort(
        key=lambda p: (
            _gender_score(p),
            0 if "sing" in p.tag else 1,
            0 if "nomn" in p.tag else 1,
        )
    )

    for parsed in typed:
        if "nomn" in parsed.tag:
            return restore_case(cleaned, parsed.word)
        inflected = parsed.inflect({"nomn"})
        if inflected is not None and inflected.word:
            return restore_case(cleaned, inflected.word)

    return cleaned


def restore_case(original: str, normalized: str) -> str:
    """Вернуть регистр первой буквы исходного слова в нормализованное."""
    if not original or not normalized:
        return normalized
    if original[0].isupper():
        return normalized[:1].upper() + normalized[1:]
    return normalized


__all__ = ["detect_gender", "to_nominative", "restore_case"]
