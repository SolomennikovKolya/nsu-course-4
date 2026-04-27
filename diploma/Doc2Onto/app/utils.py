from dataclasses import asdict, fields
from typing import Optional


def smart_asdict(obj):
    """
    Преобразует dataclass в dict, исключая поля с metadata={'skip_dict': True}.

    Используется для сохранения объектов, когда нужно исключить некоторые поля
    (например, объекты, которые загружаются динамически).

    Args:
        obj: Dataclass объект для преобразования

    Returns:
        dict: Словарь с исключёнными полями
    """
    full_dict = asdict(obj)
    return {
        f.name: full_dict[f.name]
        for f in fields(obj)
        if not f.metadata.get('skip_dict', False)
    }


def merge_exceptions(*exceptions: Optional[Exception]) -> Optional[Exception]:
    """Объединяет список исключений в одну цепочку."""
    final_ex = None
    for ex in exceptions:
        if ex is None:
            continue
        if final_ex is None:
            final_ex = ex
        else:
            tail = final_ex
            while tail.__cause__ is not None:
                tail = tail.__cause__
            tail.__cause__ = ex

    return final_ex


def exception_chain_to_message(ex: Optional[Exception]) -> Optional[str]:
    """
    Преобразует цепочку исключений (__cause__) в строку:
    "<текст исключения 1>; <текст исключения 2>; ..."
    """
    if ex is None:
        return None

    parts = []
    visited: set[int] = set()
    current: Optional[BaseException] = ex

    while current is not None:
        current_id = id(current)
        if current_id in visited:
            parts.append("<cycle in exception chain>")
            break
        visited.add(current_id)

        msg = str(current).strip()
        parts.append(msg or current.__class__.__name__)
        current = current.__cause__

    return "; ".join(parts)


def merge_messages(*messages: Optional[str]) -> Optional[str]:
    """Объединяет список ошибок в одну строку."""
    msgs = [m for m in messages if m]
    if not msgs:
        return None

    return "; ".join(msgs)
