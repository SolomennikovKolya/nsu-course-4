import re
from typing import Callable, List, Optional, Pattern


ValidationRule = Callable[[str], Optional[str]]


def _parse_float(value: str) -> Optional[float]:
    s = value.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(value: str) -> Optional[int]:
    s = value.strip()
    if not s:
        return None
    try:
        return int(s, 10)
    except ValueError:
        return None


def _parse_numeric(value: str) -> Optional[float]:
    """Целое или вещественное число в строке."""
    vi = _parse_int(value)
    if vi is not None:
        return float(vi)
    return _parse_float(value)


def _word_count(value: str) -> int:
    return len([w for w in value.split() if w])


class FieldValidator:
    """
    Валидатор извлечённого значения поля.

    Строится как цепочка правил (аналогично селектору и экстрактору). Каждое правило проверяет строковое значение и 
    при нарушении возвращает сообщение об ошибке. На вход каждому правилу подаётся непустая строка (значение поля). 
    """

    def __init__(self):
        self._rules: List[ValidationRule] = []

    def _validate(self, value: str) -> Optional[str]:
        """
        Применяет все правила проверки по порядку. 
        Возвращает сообщение об ошибке, если есть, иначе None.
        """
        for rule in self._rules:
            message = rule(value)
            if message is not None:
                return message
        return None

    def min_length(self, n: int) -> "FieldValidator":
        """Минимальная длина строки (после `strip`)."""
        def rule(value: str) -> Optional[str]:
            text = value.strip()
            if len(text) < n:
                return f"Длина меньше {n} символов"
            return None

        self._rules.append(rule)
        return self

    def max_length(self, n: int) -> "FieldValidator":
        """Максимальная длина строки (после `strip`)."""
        def rule(value: str) -> Optional[str]:
            text = value.strip()
            if len(text) > n:
                return f"Длина больше {n} символов"
            return None

        self._rules.append(rule)
        return self

    def integer(self) -> "FieldValidator":
        """Значение должно быть целым числом в десятичной записи."""
        def rule(value: str) -> Optional[str]:
            if _parse_int(value) is None:
                return "Ожидается целое число"
            return None

        self._rules.append(rule)
        return self

    def float_number(self) -> "FieldValidator":
        """Значение должно приводиться к вещественному числу (допускается запятая как разделитель)."""
        def rule(value: str) -> Optional[str]:
            if _parse_float(value) is None:
                return "Ожидается вещественное число"
            return None

        self._rules.append(rule)
        return self

    def numeric(self) -> "FieldValidator":
        """Значение должно быть целым или вещественным числом."""
        def rule(value: str) -> Optional[str]:
            if _parse_numeric(value) is None:
                return "Некорректное числовое значение"
            return None

        self._rules.append(rule)
        return self

    def alphabetic(self) -> "FieldValidator":
        """Проверяет, что строка содержит только буквы и пробелы."""
        def rule(value: str) -> Optional[str]:
            if any(not (ch.isalpha() or ch.isspace()) for ch in value):
                return "Допустимы только буквы и пробелы"
            return None

        self._rules.append(rule)
        return self

    def no_letters(self) -> "FieldValidator":
        """Проверяет, что строка содержит только цифры, пробелы и спецсимволы (без букв)."""
        def rule(value: str) -> Optional[str]:
            if any(ch.isalpha() for ch in value):
                return "Буквы недопустимы: разрешены только цифры и спецсимволы"
            return None

        self._rules.append(rule)
        return self

    def regex(self, pattern: str | Pattern[str], *, flags: int = 0, full_match: bool = False) -> "FieldValidator":
        """
        Проверка по регулярному выражению.
        По умолчанию — как `re.match`: совпадение с начала строки (хвост может быть любым).
        При `full_match=True` — вся строка должна совпадать с шаблоном.
        """
        compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

        def rule(value: str) -> Optional[str]:
            if full_match:
                if compiled.fullmatch(value) is None:
                    return f"Не соответствует шаблону: {compiled.pattern}"
            else:
                if compiled.match(value) is None:
                    return f"Не соответствует шаблону: {compiled.pattern}"
            return None

        self._rules.append(rule)
        return self

    def in_range(self, min_val: int | float, max_val: int | float) -> "FieldValidator":
        """Число (целое или вещественное) должно лежать в отрезке `[min_val, max_val]` (включительно)."""
        lo, hi = float(min_val), float(max_val)

        def rule(value: str) -> Optional[str]:
            v = _parse_numeric(value)
            if v is None:
                return "Некорректное числовое значение"
            if not (lo <= v <= hi):
                return f"Значение вне диапазона [{min_val}, {max_val}]"
            return None

        self._rules.append(rule)
        return self

    def less_than(self, bound: int | float, *, inclusive: bool = False) -> "FieldValidator":
        """Число должно быть строго меньше `bound` (или `<=` при `inclusive=True`)."""
        b = float(bound)

        def rule(value: str) -> Optional[str]:
            v = _parse_numeric(value)
            if v is None:
                return "Некорректное числовое значение"
            if inclusive:
                if v > b:
                    return f"Значение должно быть не больше {bound}"
            else:
                if v >= b:
                    return f"Значение должно быть меньше {bound}"
            return None

        self._rules.append(rule)
        return self

    def greater_than(self, bound: int | float, *, inclusive: bool = False) -> "FieldValidator":
        """Число должно быть строго больше `bound` (или `>=` при `inclusive=True`)."""
        b = float(bound)

        def rule(value: str) -> Optional[str]:
            v = _parse_numeric(value)
            if v is None:
                return "Некорректное числовое значение"
            if inclusive:
                if v < b:
                    return f"Значение должно быть не меньше {bound}"
            else:
                if v <= b:
                    return f"Значение должно быть больше {bound}"
            return None

        self._rules.append(rule)
        return self

    def word_count(self, *, exact: Optional[int] = None, min_words: Optional[int] = None, max_words: Optional[int] = None) -> "FieldValidator":
        """
        Проверка количества «слов» (последовательностей непробельных символов, разделённых пробелами).

        Задаётся либо `exact`, либо границы `min_words` / `max_words` (можно комбинировать min/max).
        """
        if exact is not None and (min_words is not None or max_words is not None):
            raise ValueError("Укажите либо exact, либо min_words/max_words")

        def rule(value: str) -> Optional[str]:
            text = value.strip()
            n = _word_count(text)
            if exact is not None:
                if n != exact:
                    return f"Ожидается ровно {exact} слов(а), получено {n}"
                return None
            if min_words is not None and n < min_words:
                return f"Минимум {min_words} слов(а), получено {n}"
            if max_words is not None and n > max_words:
                return f"Максимум {max_words} слов(а), получено {n}"
            return None

        self._rules.append(rule)
        return self

    def apply(self, rule: ValidationRule) -> "FieldValidator":
        """
        Пользовательское правило с сигнатурой `(value) -> Optional[str]`. 
        Правило принимает строку (значение поля) и должно возвращать сообщение об ошибке, если есть, иначе None.
        """
        self._rules.append(rule)
        return self


def val() -> FieldValidator:
    """Создаёт валидатор поля."""
    return FieldValidator()
