import re
from typing import Callable, List, Optional, Pattern

from core.uddm.model import UDDM, Root, P, Element, ElementType, ELEMENT_TYPE_TO_CLASS
from core.uddm.algorithms import build_parent_index


ElementPredicate = Callable[[Element], bool]
ScopeOperation = Callable[[List[Element]], List[Element]]


def contains_text(text: str, *, case_sensitive: bool = False) -> ElementPredicate:
    """Предикат: строковое представление элемента содержит подстроку."""
    needle = text if case_sensitive else text.lower()

    def _predicate(el: Element) -> bool:
        haystack = str(el) if case_sensitive else str(el).lower()
        return needle in haystack

    return _predicate


def matches_regex(pattern: str | Pattern[str], *, flags: int = 0) -> ElementPredicate:
    """Предикат: строковое представление элемента матчится с регулярным выражением."""
    compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
    return lambda el: compiled.search(str(el)) is not None


def starts_with(prefix: str, *, case_sensitive: bool = False) -> ElementPredicate:
    """Предикат: строковое представление элемента начинается с префикса."""
    needle = prefix if case_sensitive else prefix.lower()

    def _predicate(el: Element) -> bool:
        text = str(el) if case_sensitive else str(el).lower()
        return text.startswith(needle)

    return _predicate


def ends_with(suffix: str, *, case_sensitive: bool = False) -> ElementPredicate:
    """Предикат: строковое представление элемента заканчивается суффиксом."""
    needle = suffix if case_sensitive else suffix.lower()

    def _predicate(el: Element) -> bool:
        text = str(el) if case_sensitive else str(el).lower()
        return text.endswith(needle)

    return _predicate


def min_length(n: int) -> ElementPredicate:
    """Предикат: длина строки элемента не меньше n."""
    return lambda el: len(str(el)) >= n


def max_length(n: int) -> ElementPredicate:
    """Предикат: длина строки элемента не больше n."""
    return lambda el: len(str(el)) <= n


def all_of(*predicates: ElementPredicate) -> ElementPredicate:
    """Комбинация предикатов через логическое И."""
    return lambda el: all(pred(el) for pred in predicates)


def any_of(*predicates: ElementPredicate) -> ElementPredicate:
    """Комбинация предикатов через логическое ИЛИ."""
    return lambda el: any(pred(el) for pred in predicates)


def invert(predicate: ElementPredicate) -> ElementPredicate:
    """Инверсия предиката."""
    return lambda el: not predicate(el)


class FieldSelector:
    """
    Селектор полей — инструмент для пошагового отбора нужного текста из структуры документа UDDM с помощью набора операций. 
    Используйте этот класс для построения цепочки методов (например, `.find(...)`, `.next_element()` и т.д.), которая на каждом 
    этапе сужает область поиска от всего документа до одного или нескольких элементов UDDM, подходящих под заданные условия. 

    Этот механизм позволяет точно указать, как из дерева документа выбрать то содержимое, которое требуется для поля шаблона.
    После применения всей цепочки операций к документу, результат (обычно параграф или несколько параграфов) 
    преобразуется в строку и передается экстрактору для окончательного извлечения значения поля.

    Если после применения цепочки фильтров осталось несколько подходящих элементов, для дальнейшей обработки 
    автоматически используется первый из них. Если необходимо выбрать какой-то конкретный элемент, используйте 
    `.first()`, `.last()` или `.at(index)` в конце цепочки операций.

    Таким образом, `FieldSelector` — это удобный декларативный способ нахождения нужного элемента в дереве документа.
    """

    def __init__(self):
        self._operations: List[Callable[[...], List[Element]]] = []  # Цепочка операций
        self._scope: List[Element] = []                              # Текущая область поиска
        self._parent_index: dict[Element, tuple[Element, int]] = {}  # Индекс родителей

    def _select(self, uddm: UDDM) -> Optional[str]:
        """
        Внутренний метод, используемый экстрактором, который запускает цепочку операций 
        и возвращает результат в виде строки.
        """
        # Начальная область поиска - всё дерево UDDM
        self._scope = [uddm.root]
        self._parent_index = build_parent_index(uddm.root)

        # Последовательное применение операции для сужения области поиска
        for op in self._operations:
            self._scope = op()

        if len(self._scope) == 0:
            return None

        # Считаем, что финальной областью поиска не может быть корень документа
        if len(self._scope) == 1 and isinstance(self._scope[0], Root):
            return None

        # Вконце должна остаться единственная локальная область поиска. Если это не так, то возвращаем первую
        result = str(self._scope[0])
        return result

    def find(self, element_type: ElementType, predicate: ElementPredicate) -> "FieldSelector":
        """
        Находит все элементы заданного типа в дереве UDDM, удовлетворяющие заданному предикату.

        Если `find` стоит в начале цепочки операций, то поиск будет осуществлён в глобальной области
        (т.е. во всём дереве UDDM, начиная с корня). Если же `find` стоит в середине цепочки операций,
        то поиск будет осуществлён в каждой из локальных областей, являющимися результатом предыдущей операции.
        Таким образом `find` сужает область поиска на каждом шаге.

        Если в одной области вложены несколько узлов подходящего типа и все они удовлетворяют предикату,
        в новую область попадают только самые внутренние (листья среди совпадений в этом поддереве).

        Args:
            element_type (ElementType): Тип элементов, которые требуется найти (например, ElementType.P, ElementType.TABLE и т.д.).
            predicate (Callable[[Element], bool]): Функция-предикат, к каждому найденному элементу применяется данный фильтр.

        Returns:
            FieldSelector: Тот же селектор для построения цепочки операций.
        """
        cls = ELEMENT_TYPE_TO_CLASS[element_type]

        def dfs(v: Element, found: List[Element]) -> bool:
            if not isinstance(v, P):
                for child in v:
                    if dfs(child, found):
                        return True

            if isinstance(v, cls) and predicate(v):
                found.append(v)
                return True
            return False

        def op() -> List[Element]:
            found: List[Element] = []
            for scope_root in self._scope:
                dfs(scope_root, found)
            return found

        self._operations.append(op)
        return self

    def next_element(self) -> "FieldSelector":
        """
        Смещает каждую локальную область поиска к следующему соседнему элементу.
        Пример: для Cell это клетка справа.
        Если следующего элемента нет, область удаляется из результата.
        """
        def next_sibling(el: Element) -> Optional[Element]:
            rel = self._parent_index.get(el)
            if rel is None:
                return None

            parent, idx = rel
            if idx + 1 >= len(parent):
                return None
            return parent[idx + 1]

        def op() -> List[Element]:
            result: List[Element] = []
            for scope_root in self._scope:
                moved = next_sibling(scope_root)
                if moved is not None:
                    result.append(moved)
            return result

        self._operations.append(op)
        return self

    def previous_element(self) -> "FieldSelector":
        """
        Смещает каждую локальную область поиска к предыдущему соседнему элементу.
        Пример: для Cell это клетка слева.
        Если предыдущего элемента нет, область удаляется из результата.
        """
        def previous_sibling(el: Element) -> Optional[Element]:
            rel = self._parent_index.get(el)
            if rel is None:
                return None

            parent, idx = rel
            if idx - 1 < 0:
                return None
            return parent[idx - 1]

        def op() -> List[Element]:
            result: List[Element] = []
            for scope_root in self._scope:
                moved = previous_sibling(scope_root)
                if moved is not None:
                    result.append(moved)
            return result

        self._operations.append(op)
        return self

    def inner_element(self, index: int) -> "FieldSelector":
        """
        Смещает каждую локальную область поиска к index-му вложенному элементу (0-based).
        Индекс может быть отрицательным, тогда он считается с конца.
        Пример: для ListBlock index=-1 даст последний Item.
        Если элемента с таким индексом нет, область удаляется из результата.
        """
        def child_at(el: Element, index: int) -> Optional[Element]:
            if isinstance(el, P):
                return None
            if index < -len(el) or index >= len(el):
                return None
            return el[index]

        def op() -> List[Element]:
            result: List[Element] = []
            for scope_root in self._scope:
                moved = child_at(scope_root, index)
                if moved is not None:
                    result.append(moved)
            return result

        self._operations.append(op)
        return self

    def outer_element(self) -> "FieldSelector":
        """
        Смещает каждую локальную область поиска к внешнему элементу (родителю).
        Пример: для Cell это Row.
        Если внешнего элемента нет, область удаляется из результата.
        """
        def op() -> List[Element]:
            result: List[Element] = []
            for scope_root in self._scope:
                rel = self._parent_index.get(scope_root)
                if rel is not None:
                    result.append(rel[0])
            return result

        self._operations.append(op)
        return self

    def first(self) -> "FieldSelector":
        """
        Оставляет только первую локальную область поиска.
        Если область поиска пуста, возвращает пустой список.
        """
        def op() -> List[Element]:
            if not self._scope:
                return []
            return [self._scope[0]]

        self._operations.append(op)
        return self

    def last(self) -> "FieldSelector":
        """
        Оставляет только последнюю локальную область поиска.
        Если область поиска пуста, возвращает пустой список.
        """
        def op() -> List[Element]:
            if not self._scope:
                return []
            return [self._scope[-1]]

        self._operations.append(op)
        return self

    def at(self, index: int) -> "FieldSelector":
        """
        Оставляет только локальную область поиска с заданным индексом.
        Поддерживает отрицательные индексы (как в списках Python).
        Если индекс вне диапазона, возвращает пустой список.
        """
        def op() -> List[Element]:
            if index < -len(self._scope) or index >= len(self._scope):
                return []
            return [self._scope[index]]

        self._operations.append(op)
        return self

    def apply(self, operation: ScopeOperation) -> "FieldSelector":
        """
        Добавляет в цепочку кастомную операцию над текущим списком локальных областей поиска.

        Args:
            operation (Callable[[List[Element]], List[Element]]):
                Пользовательская функция, которая получает текущую область поиска
                (список локальных областей) и возвращает новую область.

        Returns:
            FieldSelector: Тот же селектор для продолжения цепочки.
        """
        def op() -> List[Element]:
            return operation(self._scope)

        self._operations.append(op)
        return self


def select() -> FieldSelector:
    """Создаёт селектор полей."""
    return FieldSelector()
