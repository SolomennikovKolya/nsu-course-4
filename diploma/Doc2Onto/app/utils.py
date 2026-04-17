from dataclasses import asdict, fields


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
