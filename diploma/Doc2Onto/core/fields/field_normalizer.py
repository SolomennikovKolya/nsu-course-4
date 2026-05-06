"""
Цепочечный нормализатор значения поля.

Заменяет старый ``FieldValidator``: вместо «проверить — вернуть ошибку»
делает «проверить и нормализовать — вернуть каноническую строку или
None». Это убирает противоречие, при котором валидатор сообщал об
ошибке формы, а ValueTransformer ниже по пайплайну её всё равно
исправлял (например «ФИО не в именительном падеже» → морфология
приводит к именительному).

Знания, специфичные для предметной области (ФИО, дата, номер группы и
т. п.), сосредоточены в концептах :mod:`core.concepts`. Чтобы не
размазывать ontology-зависимый код по DSL, в нормализаторе нет
одноимённых методов вида ``person()`` / ``date_iso()`` / ``group_number()``;
вместо них есть ОДИН универсальный метод :meth:`FieldNormalizer.concept`,
которому передаётся подкласс :class:`BaseConcept`.

Примеры::

    norm()                                    # bare: только trim, всё валидно
    norm().concept(PersonConcept)             # ФИО → именительный падеж
    norm().concept(DateConcept)               # дата в любом формате → ISO
    norm().concept(GroupConcept)              # номер группы (любая форма)

    # Поля без концепта — по-прежнему доступны примитивы:
    norm().integer().in_range(1, 4)           # курс
    norm().regex(r"\\d{2}\\.\\d{2}\\.\\d{2}", full_match=True)  # код

Любой ``rule`` в цепочке либо возвращает строку (передаётся следующему
правилу), либо None (значение отвергнуто, цепочка останавливается, и
``last_error`` хранит сообщение). Цепочка автоматически делает ``strip``
на входе и отвергает пустое значение до первого правила.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Pattern, Tuple, Type

from core.concepts.base import BaseConcept, ConceptError


# Правило нормализации: (value) -> новая строка | None.
# Возврат None означает «значение не соответствует правилу».
NormalizationRule = Callable[[str], Optional[str]]


# ---------------------------------------------------------------------------
# Помощники парсинга чисел (повторяют поведение старого FieldValidator).
# ---------------------------------------------------------------------------


def _parse_int(value: str) -> Optional[int]:
    s = value.strip()
    if not s:
        return None
    try:
        return int(s, 10)
    except ValueError:
        return None


def _parse_float(value: str) -> Optional[float]:
    s = value.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_numeric(value: str) -> Optional[float]:
    vi = _parse_int(value)
    if vi is not None:
        return float(vi)
    return _parse_float(value)


def _word_count(value: str) -> int:
    return len([w for w in value.split() if w])


# ---------------------------------------------------------------------------
# Класс
# ---------------------------------------------------------------------------


class FieldNormalizer:
    """Цепочка правил нормализации значения поля.

    Контракт правила: получает непустую строку (после ``strip``), возвращает
    либо новую строку (она передаётся следующему правилу как новое
    значение), либо ``None`` (значение отвергнуто, цепочка
    останавливается). При отвержении правило обязано предварительно
    вызвать :meth:`_reject` или поднять исключение — иначе
    нормализатор подставит дефолтное сообщение «Не прошло правило».

    Метод :meth:`_normalize` возвращает каноническую строку или ``None``.
    Сообщение об ошибке доступно в :attr:`last_error`.
    """

    def __init__(self) -> None:
        self._rules: List[Tuple[str, NormalizationRule]] = []
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Запуск
    # ------------------------------------------------------------------

    def _normalize(self, value: Optional[str]) -> Optional[str]:
        """Применить цепочку. Вернуть каноническую строку или None."""
        self._last_error = None
        if value is None:
            self._last_error = "Значение пустое"
            return None

        current = str(value).strip()
        if not current:
            self._last_error = "Значение пустое"
            return None

        for label, rule in self._rules:
            try:
                result = rule(current)
            except Exception as ex:
                self._last_error = f"{label}: {ex}"
                return None

            if result is None:
                if self._last_error is None:
                    self._last_error = f"Не прошло правило «{label}»"
                return None
            current = result

        return current

    @property
    def last_error(self) -> Optional[str]:
        """Сообщение об ошибке после последнего вызова :meth:`_normalize`
        (None, если значение прошло цепочку)."""
        return self._last_error

    def _reject(self, message: str) -> None:
        """Установить сообщение об ошибке (для использования внутри правил)."""
        self._last_error = message

    # ------------------------------------------------------------------
    # Универсальные методы
    # ------------------------------------------------------------------

    def concept(self, concept_cls: Type[BaseConcept]) -> "FieldNormalizer":
        """Делегировать парсинг и нормализацию подклассу :class:`BaseConcept`.

        Заменяет значение на ``concept_cls.normalize(value)``. Работает
        для любого вида концепта (``CLASS_INDIVIDUAL`` или ``DATATYPE``)
        — на этапе нормализации разница не проявляется, она важна только
        при сборке графа.

        Если концепт отвергает значение (поднимает :class:`ConceptError`),
        правило фиксирует сообщение об ошибке и возвращает None.

        Это ОСНОВНОЙ способ привязать поле к онтологии. Вместо
        ``val().alphabetic().word_count(2,3)`` для ФИО пишется
        ``norm().concept(PersonConcept)``: морфологическое приведение к
        именительному падежу, проверка наличия фамилии и инициала имени
        — всё внутри концепта.

        Args:
            concept_cls: Подкласс :class:`BaseConcept` (например
                ``PersonConcept``, ``DateConcept``, ``GroupConcept``).

        Raises:
            TypeError: если ``concept_cls`` не подкласс ``BaseConcept``.
        """
        if not (isinstance(concept_cls, type) and issubclass(concept_cls, BaseConcept)):
            raise TypeError(
                f"concept(): ожидается подкласс BaseConcept, получено {concept_cls!r}"
            )

        label = f"concept:{concept_cls.name}"

        def rule(text: str) -> Optional[str]:
            try:
                return concept_cls.normalize(text)
            except ConceptError as ex:
                self._reject(str(ex))
                return None

        self._rules.append((label, rule))
        return self

    def apply(
        self,
        fn: NormalizationRule,
        *,
        label: str = "apply",
    ) -> "FieldNormalizer":
        """Пользовательское правило ``(value) -> Optional[str]``.

        Возврат строки — нормализованное значение для следующего правила;
        возврат ``None`` — значение отвергнуто. Если правило хочет дать
        конкретное сообщение, оно должно вызвать ``self._reject(...)``
        через замыкание перед возвратом None — иначе пользователь увидит
        дефолтное «Не прошло правило ``<label>``».

        Args:
            fn: Функция-правило.
            label: Метка для диагностических сообщений.
        """
        self._rules.append((label, fn))
        return self

    # ------------------------------------------------------------------
    # Примитивы формата (значение проходит сквозь без изменений на успехе)
    # ------------------------------------------------------------------

    def regex(
        self,
        pattern: str | Pattern[str],
        *,
        flags: int = 0,
        full_match: bool = False,
    ) -> "FieldNormalizer":
        """Проверка по регулярному выражению. Значение не меняется.

        Args:
            pattern: Шаблон или скомпилированный re.Pattern.
            flags: Флаги при компиляции строкового шаблона.
            full_match: ``True`` — шаблон должен покрывать всю строку
                (``fullmatch``); ``False`` (по умолчанию) — должен начинаться
                с начала строки (``match``).
        """
        compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

        def rule(text: str) -> Optional[str]:
            ok = compiled.fullmatch(text) if full_match else compiled.match(text)
            if ok is None:
                self._reject(f"Не соответствует шаблону: {compiled.pattern}")
                return None
            return text

        self._rules.append((f"regex({compiled.pattern})", rule))
        return self

    def integer(self) -> "FieldNormalizer":
        """Целое число в десятичной записи. Значение не меняется."""
        def rule(text: str) -> Optional[str]:
            if _parse_int(text) is None:
                self._reject("Ожидается целое число")
                return None
            return text
        self._rules.append(("integer", rule))
        return self

    def numeric(self) -> "FieldNormalizer":
        """Целое или вещественное число (запятая допустима как разделитель)."""
        def rule(text: str) -> Optional[str]:
            if _parse_numeric(text) is None:
                self._reject("Некорректное числовое значение")
                return None
            return text
        self._rules.append(("numeric", rule))
        return self

    def in_range(self, min_val: int | float, max_val: int | float) -> "FieldNormalizer":
        """Число в диапазоне ``[min_val, max_val]`` (включительно)."""
        lo, hi = float(min_val), float(max_val)

        def rule(text: str) -> Optional[str]:
            v = _parse_numeric(text)
            if v is None:
                self._reject("Некорректное числовое значение")
                return None
            if not (lo <= v <= hi):
                self._reject(f"Значение вне диапазона [{min_val}, {max_val}]")
                return None
            return text

        self._rules.append((f"in_range[{min_val},{max_val}]", rule))
        return self

    def less_than(self, bound: int | float, *, inclusive: bool = False) -> "FieldNormalizer":
        """Число строго меньше ``bound`` (или ``<=`` при ``inclusive=True``)."""
        b = float(bound)

        def rule(text: str) -> Optional[str]:
            v = _parse_numeric(text)
            if v is None:
                self._reject("Некорректное числовое значение")
                return None
            if inclusive and v > b:
                self._reject(f"Значение должно быть не больше {bound}")
                return None
            if not inclusive and v >= b:
                self._reject(f"Значение должно быть меньше {bound}")
                return None
            return text

        self._rules.append((f"less_than({bound})", rule))
        return self

    def greater_than(self, bound: int | float, *, inclusive: bool = False) -> "FieldNormalizer":
        """Число строго больше ``bound`` (или ``>=`` при ``inclusive=True``)."""
        b = float(bound)

        def rule(text: str) -> Optional[str]:
            v = _parse_numeric(text)
            if v is None:
                self._reject("Некорректное числовое значение")
                return None
            if inclusive and v < b:
                self._reject(f"Значение должно быть не меньше {bound}")
                return None
            if not inclusive and v <= b:
                self._reject(f"Значение должно быть больше {bound}")
                return None
            return text

        self._rules.append((f"greater_than({bound})", rule))
        return self

    def alphabetic(self) -> "FieldNormalizer":
        """Только буквы и пробелы. Значение не меняется."""
        def rule(text: str) -> Optional[str]:
            if any(not (ch.isalpha() or ch.isspace()) for ch in text):
                self._reject("Допустимы только буквы и пробелы")
                return None
            return text
        self._rules.append(("alphabetic", rule))
        return self

    def word_count(
        self,
        *,
        exact: Optional[int] = None,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
    ) -> "FieldNormalizer":
        """Количество «слов» (последовательности непробельных символов).

        Указывается либо ``exact``, либо ``min_words``/``max_words`` (можно
        в любой комбинации). Значение не меняется.
        """
        if exact is not None and (min_words is not None or max_words is not None):
            raise ValueError("Укажите либо exact, либо min_words/max_words")

        def rule(text: str) -> Optional[str]:
            n = _word_count(text)
            if exact is not None:
                if n != exact:
                    self._reject(f"Ожидается ровно {exact} слов(а), получено {n}")
                    return None
                return text
            if min_words is not None and n < min_words:
                self._reject(f"Минимум {min_words} слов(а), получено {n}")
                return None
            if max_words is not None and n > max_words:
                self._reject(f"Максимум {max_words} слов(а), получено {n}")
                return None
            return text

        self._rules.append(("word_count", rule))
        return self

    def min_length(self, n: int) -> "FieldNormalizer":
        """Минимальная длина строки (после ``strip``). Значение не меняется."""
        def rule(text: str) -> Optional[str]:
            if len(text) < n:
                self._reject(f"Длина меньше {n} символов")
                return None
            return text
        self._rules.append((f"min_length({n})", rule))
        return self

    def max_length(self, n: int) -> "FieldNormalizer":
        """Максимальная длина строки (после ``strip``). Значение не меняется."""
        def rule(text: str) -> Optional[str]:
            if len(text) > n:
                self._reject(f"Длина больше {n} символов")
                return None
            return text
        self._rules.append((f"max_length({n})", rule))
        return self

    # ------------------------------------------------------------------
    # Преобразования (меняют значение)
    # ------------------------------------------------------------------

    def lowercase(self) -> "FieldNormalizer":
        """Перевод значения в нижний регистр."""
        self._rules.append(("lowercase", lambda t: t.lower()))
        return self

    def collapse_spaces(self) -> "FieldNormalizer":
        """Все последовательности пробельных символов → одиночный пробел."""
        self._rules.append(("collapse_spaces", lambda t: " ".join(t.split())))
        return self

    def replace(self, old: str, new: str) -> "FieldNormalizer":
        """Замена подстроки во всех вхождениях."""
        self._rules.append((f"replace({old!r},{new!r})", lambda t: t.replace(old, new)))
        return self


def norm() -> FieldNormalizer:
    """Создать пустой нормализатор (без правил → только ``strip`` входа)."""
    return FieldNormalizer()


__all__ = ["FieldNormalizer", "NormalizationRule", "norm"]
