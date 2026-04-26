from typing import Optional, Dict


class FieldsAccessor:
    """Аксессор для получения значений извлечённых полей."""

    def __init__(self, filed_values: Dict[str, str]):
        self._field_values = filed_values

    def value(self, name: str) -> Optional[str]:
        return self._field_values.get(name, None)
