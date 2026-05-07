import re
from typing import Callable, List, Optional, Pattern


ExtractOperation = Callable[[str], Optional[str]]


# Базовый набор «шаблонных» подписей, которые встречаются в формах документов
# и должны вычищаться перед последующей нормализацией. Регулярки максимально
# консервативные: убирают только те паттерны, которые в осмысленных значениях
# (ФИО, дата, номер группы и т. п.) встречаться не могут.
_TEMPLATE_PAREN_RE = re.compile(
    r"\(\s*(?:ф\s*\.?\s*и\s*\.?\s*о\s*\.?|фио|должность|дата|подпись|инициалы|"
    r"при\s+наличии|если\s+имеется|расшифровка(?:\s+подписи)?|"
    r"наименование(?:\s+\w+){0,3}|номер|шифр)\s*\)",
    re.IGNORECASE,
)
# Метка-префикс вида «ФИО:», «Дата:», «Группа №» в начале строки.
_TEMPLATE_LABEL_RE = re.compile(
    r"^\s*(?:ф\s*\.?\s*и\s*\.?\s*о\s*\.?|фио|дата|группа(?:\s*№)?|должность|подпись|"
    r"тема(?:\s+вкр)?|руководитель(?:\s+вкр)?|студент|научный\s+руководитель|"
    r"кафедра|факультет|направление\s+подготовки|профиль|уч\.?\s*год|учебный\s+год)"
    r"\s*[:\-—]\s*",
    re.IGNORECASE,
)
# Заполнители: длинные подчёркивания, многоточия, длинные тире-сепараторы.
_TEMPLATE_FILLERS_RE = re.compile(r"_{2,}|\.{3,}|—{2,}|-{3,}")


class FieldExtractor:
    """
    Экстрактор значения поля из строки.

    Работает как цепочка операций преобразования текста:
    каждая операция получает строку и возвращает новую строку
    или None (если извлечение на этом шаге невозможно).
    """

    def __init__(self):
        self._operations: List[ExtractOperation] = []

    def _extract(self, text: str) -> Optional[str]:
        """
        Запускает цепочку операций и возвращает итоговое значение поля
        в виде одной строки (или None, если извлечь не удалось).
        """
        value: Optional[str] = text

        for op in self._operations:
            value = op(value)
            if value is None:
                return None

        value = value.strip()
        return value or None

    def regex(self, pattern: str | Pattern[str], group: int | str = 0, flags: int = 0) -> "FieldExtractor":
        """Извлекает первое совпадение regex (или указанную группу)."""
        compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

        def op(text: str) -> Optional[str]:
            match = compiled.search(text)
            if not match:
                return None
            try:
                return match.group(group)
            except (IndexError, KeyError):
                return None

        self._operations.append(op)
        return self

    def after(self, marker: str, *, case_sensitive: bool = False) -> "FieldExtractor":
        """Оставляет часть строки после маркера."""
        def op(text: str) -> Optional[str]:
            if case_sensitive:
                idx = text.find(marker)
            else:
                idx = text.lower().find(marker.lower())
            if idx == -1:
                return None
            return text[idx + len(marker):]

        self._operations.append(op)
        return self

    def before(self, marker: str, *, case_sensitive: bool = False) -> "FieldExtractor":
        """Оставляет часть строки до маркера."""
        def op(text: str) -> Optional[str]:
            if case_sensitive:
                idx = text.find(marker)
            else:
                idx = text.lower().find(marker.lower())
            if idx == -1:
                return None
            return text[:idx]

        self._operations.append(op)
        return self

    def between(self,
                left: str, right: str, *,
                include_left: bool = False, include_right: bool = False,
                case_sensitive: bool = False) -> "FieldExtractor":
        """
        Извлекает подстроку между левым (`left`) и правым (`right`) маркером в исходном тексте.

        Args:
            left (str): Левый маркер (подстрока, от которой начинается извлечение).
            right (str): Правый маркер (подстрока, до которой заканчивается извлечение).
            include_left (bool, optional): Включить ли левый маркер в результат. По умолчанию False.
            include_right (bool, optional): Включить ли правый маркер в результат. По умолчанию False.
            case_sensitive (bool, optional): Учитывать ли регистр при поиске маркеров. По умолчанию False.

        Returns:
            FieldExtractor: Текущий экстрактор для цепочки операций.

        Если один из маркеров не найден, возвращает None.
        """
        def op(text: str) -> Optional[str]:
            source = text if case_sensitive else text.lower()
            left_src = left if case_sensitive else left.lower()
            right_src = right if case_sensitive else right.lower()

            left_idx = source.find(left_src)
            if left_idx == -1:
                return None

            content_start = left_idx if include_left else left_idx + len(left)
            search_right_from = left_idx + len(left_src)
            right_idx = source.find(right_src, search_right_from)
            if right_idx == -1:
                return None

            content_end = right_idx + len(right) if include_right else right_idx
            return text[content_start:content_end]

        self._operations.append(op)
        return self

    def replace(self, old: str, new: str, *, count: int = -1) -> "FieldExtractor":
        """Заменяет подстроку в текущем значении."""
        self._operations.append(lambda text: text.replace(old, new, count))
        return self

    def normalize_spaces(self) -> "FieldExtractor":
        """Сжимает все последовательности whitespace в одиночный пробел."""
        self._operations.append(lambda text: " ".join(text.split()))
        return self

    def trim(self) -> "FieldExtractor":
        """Обрезает пробелы по краям строки."""
        self._operations.append(lambda text: text.strip())
        return self

    def prefix(self, value: str) -> "FieldExtractor":
        """Добавляет префикс к строке."""
        self._operations.append(lambda text: f"{value}{text}")
        return self

    def suffix(self, value: str) -> "FieldExtractor":
        """Добавляет суффикс к строке."""
        self._operations.append(lambda text: f"{text}{value}")
        return self

    def lower(self) -> "FieldExtractor":
        """Переводит строку в нижний регистр."""
        self._operations.append(lambda text: text.lower())
        return self

    def upper(self) -> "FieldExtractor":
        """Переводит строку в верхний регистр."""
        self._operations.append(lambda text: text.upper())
        return self

    def keep_letters_and_spaces(self) -> "FieldExtractor":
        """Оставляет только буквы (латиница/кириллица) и пробельные символы."""
        self._operations.append(lambda text: "".join(ch for ch in text if ch.isalpha() or ch.isspace()))
        return self

    def keep_digits_and_symbols(self) -> "FieldExtractor":
        """Оставляет только цифры, пробелы и спецсимволы (без букв)."""
        self._operations.append(
            lambda text: "".join(
                ch for ch in text
                if ch.isdigit() or ch.isspace() or not ch.isalnum()
            )
        )
        return self

    def keep_regex(self, pattern: str | Pattern[str], *, flags: int = 0) -> "FieldExtractor":
        """
        Оставляет только символы, которые поштучно соответствуют regex.

        Пример: ``keep_regex(r"[A-F0-9]")``.
        """
        compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        self._operations.append(lambda text: "".join(ch for ch in text if compiled.fullmatch(ch)))
        return self

    def strip_template_markers(self, *extra_markers: str) -> "FieldExtractor":
        """
        Удаляет типовые «шаблонные» подписи из текста бланков:

          * скобочные пометки в начале/середине строки (``(Ф.И.О.)``, ``(должность)``,
            ``(подпись)``, ``(дата)``, ``(при наличии)`` и т. п.);
          * лидирующие метки ``ФИО:``, ``Дата:``, ``Группа №``, ``Тема ВКР:`` и т. п.;
          * заполнители: подряд идущие подчёркивания, многоточия, длинные тире.

        Дополнительно убирает любые подстроки из ``extra_markers`` (без учёта регистра).
        После вычистки схлопывает пробелы. Возвращает None, если после удаления
        в строке не осталось содержательного текста.

        Args:
            *extra_markers: Дополнительные подстроки для удаления (если зашитого
                списка не хватает — например, специфичные подписи конкретного бланка).
        """
        compiled_extra = [
            re.compile(re.escape(m), re.IGNORECASE) for m in extra_markers if m
        ]

        def op(text: str) -> Optional[str]:
            result = _TEMPLATE_LABEL_RE.sub("", text)
            result = _TEMPLATE_PAREN_RE.sub(" ", result)
            result = _TEMPLATE_FILLERS_RE.sub(" ", result)
            for pattern in compiled_extra:
                result = pattern.sub(" ", result)
            result = re.sub(r"\s+", " ", result).strip()
            return result or None

        self._operations.append(op)
        return self

    def pick_first_match(
        self,
        *patterns: str | Pattern[str],
        group: int | str = 0,
        flags: int = 0,
    ) -> "FieldExtractor":
        """
        Перебирает регулярные выражения по порядку и возвращает результат первого совпадения.

        Удобно, когда поле может быть записано в одном из нескольких форматов
        (``Группа: 22204``, ``№ группы — 22204а``, ``группа М-2024-1``) и хочется
        перечислить все варианты, не строя один длинный «универсальный» regex.

        Args:
            *patterns: Регулярные выражения (строки или скомпилированные шаблоны)
                в порядке приоритета.
            group: Группа для извлечения из совпадения (0 — всё совпадение).
            flags: Флаги компиляции для строковых паттернов.
        """
        compiled: List[Pattern[str]] = [
            re.compile(p, flags) if isinstance(p, str) else p for p in patterns
        ]

        def op(text: str) -> Optional[str]:
            for pat in compiled:
                m = pat.search(text)
                if not m:
                    continue
                try:
                    return m.group(group)
                except (IndexError, KeyError):
                    continue
            return None

        self._operations.append(op)
        return self

    def apply(self, operation: ExtractOperation) -> "FieldExtractor":
        """Добавляет пользовательскую операцию в цепочку."""
        self._operations.append(operation)
        return self


def ext() -> FieldExtractor:
    """Создаёт экстрактор значения поля."""
    return FieldExtractor()
