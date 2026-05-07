"""
Утилиты для концептов-перечислений (Должность, УченаяСтепень, ВидПрактики и т. п.).

Перечисления — это закрытые списки именованных индивидов из онтологии:
:Должность_Доцент, :Должность_Профессор, :ВидПрактики_Учебная и т. д. У них
нет литералов (имя индивида само несёт смысл), а ``parse`` сводится к
поиску совпадения с таблицей синонимов.
"""
from typing import Iterable, Optional, Tuple


def match_enum(value: str, table: Iterable[Tuple[str, str]]) -> Optional[str]:
    """Подстрочный case-insensitive матч против таблицы синонимов.

    Если значение уже совпадает с одним из локальных имён индивидов
    (canonical-форма) — оно принимается как есть. Это даёт идемпотентность
    ``parse(parse(x).canonical)`` для перечислений: на втором проходе
    пришёл бы ``"УченаяСтепень_КандидатФизМатНаук"``, которое ни одному
    синониму не соответствует, но является валидным local-name.

    Args:
        value: Сырое значение поля.
        table: Последовательность ``(synonym, local_name)``. Порядок важен:
            более специфичные синонимы должны идти раньше общих
            (``"зав. кафедрой"`` перед ``"кафедра"``).

    Returns:
        Локальное имя индивида онтологии или ``None``, если совпадений нет.
    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    # 1. Идемпотентность: точное совпадение с любым local-name.
    table_list = list(table)
    valid_locals = {local for _, local in table_list}
    if text in valid_locals:
        return text

    # 2. Подстрочный матч по синонимам (case-insensitive, ё→е).
    text_lower = text.lower().replace("ё", "е")
    for needle, local in table_list:
        if needle in text_lower:
            return local
    return None


__all__ = ["match_enum"]
