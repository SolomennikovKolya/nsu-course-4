from functools import wraps
from dataclasses import asdict, fields


def require_attribute(attr_name: str, default=None):
    """Фабрика декораторов для проверки наличия атрибута перед выполнением метода.

    Args:
        attr_name: Имя атрибута объекта, который должен быть не None
        default: Значение для возврата, если атрибут None (по умолчанию None)
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            attr_value = getattr(self, attr_name, None)
            if attr_value is None:
                return default
            return method(self, attr_value, *args, **kwargs)
        return wrapper
    return decorator


def smart_asdict(obj):
    """Преобразует dataclass в dict, исключая поля с metadata={'skip_dict': True}.
    
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
