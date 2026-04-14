from typing import Iterator, List

from core.uddm.model import Element, P


def iter_subtree(el: Element) -> Iterator[Element]:
    """Итератор для обхода всех дочерних элементов поддерева с корнем `el`."""
    yield el

    # Все листья UDDM дерева - это абзацы (они не итерируются)
    if isinstance(el, P):
        return

    for sub in el:
        yield from iter_subtree(sub)


def euler_tin_tout(scope_root: Element) -> tuple[dict[Element, int], dict[Element, int]]:
    """
    Выполняет один обход дерева в глубину (DFS), вычисляя временные метки входа (tin) и выхода (tout)
    для каждого узла. Это позволяет эффективно (за O(1)) проверять отношение предок–потомок между узлами:
    элемент a является предком b тогда и только тогда, когда tin[a] <= tin[b] <= tout[a].
    Поддерживает работу с неплоскими структурами UDDM, включая абзацы (P) как листья дерева.
    """
    tin: dict[Element, int] = {}
    tout: dict[Element, int] = {}
    t = 0

    def dfs(v: Element) -> None:
        nonlocal t
        tin[v] = t
        t += 1
        if isinstance(v, P):
            tout[v] = t - 1
            return
        for child in v:
            dfs(child)
        tout[v] = t - 1

    dfs(scope_root)
    return tin, tout


def innermost_only(candidates: List[Element], scope_root: Element) -> List[Element]:
    """
    Возвращает только те узлы из списка candidates, которые не содержат других кандидатов в своих поддеревьях
    (т.е. являются самыми глубокими совпадениями среди вложенных друг в друга элементов).
    Это полезно, чтобы исключить из найденных совпадений все "родительские" узлы, оставив только наиболее вложенные.
    """
    if len(candidates) <= 1:
        return candidates

    tin, tout = euler_tin_tout(scope_root)

    # Сначала более глубокие (больший tin в preorder)
    # Среди уже отобранных - только листья совпадений
    ordered = sorted(candidates, key=lambda x: tin[x], reverse=True)
    result: List[Element] = []
    for c in ordered:
        # Есть ли уже отобранный узел строго внутри c?
        if any(tin[c] < tin[s] <= tout[c] for s in result):
            continue
        result.append(c)
    return result


def build_parent_index(scope_root: Element) -> dict[Element, tuple[Element, int]]:
    """
    Строит индекс соответствия «ребёнок → (родитель, индекс_ребёнка_в_родителе)» 
    для всех элементов в поддереве, корнем которого является `scope_root`.
    Позволяет быстро находить родителей и позиции вложенных элементов, 
    что полезно для навигации внутри UDDM (например, поиска следующего/предыдущего 
    или внешнего элемента относительно заданного).
    """
    parent_index: dict[Element, tuple[Element, int]] = {}

    def dfs(parent: Element):
        if isinstance(parent, P):
            return
        for idx, child in enumerate(parent):
            parent_index[child] = (parent, idx)
            dfs(child)

    dfs(scope_root)
    return parent_index
