from __future__ import annotations

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, Node, URIRef
from rdflib.util import from_n3


class DraftNode:
    """Черновой узел графа (содержит дополнительные метаданные)."""

    class Type(Enum):
        """Возможные типы узла триплета (в системе можно создать только эти типы)."""
        IRI = auto()
        LITERAL = auto()

    def __init__(
        self,
        node_type: Type,
        node: Optional[URIRef | Literal],
        error: Optional[Exception] = None,
        source: Optional[str] = None
    ):
        self.type = node_type  # тип узла
        self.rdf_node = node   # значение узла (node != None <=> error == None)
        self.error = error     # ошибка, поясняющая причину отсутствия значения
        self.source = source   # источник (название поля шаблона или None, если значение не связано с каким-либо полем)

    def is_complete(self) -> bool:
        """Проверяет, является ли узел полным (содержащим значение)."""
        return self.rdf_node is not None

    def get_rdf_node(self) -> Optional[URIRef | Literal]:
        return self.rdf_node

    def copy(self) -> DraftNode:
        """Копия узла с теми же type, rdf_node, error, source."""
        return DraftNode(self.type, self.rdf_node, self.error, self.source)

    def equals(self, other: DraftNode) -> bool:
        """Совпадение с другим узлом по сериализованному виду (как при сравнении правок)."""
        return self._to_json_dict() == other._to_json_dict()

    def _to_json_dict(self) -> Dict[str, Any]:
        n = self.rdf_node
        return {
            "kind": self.type.name,
            "n3": n.n3() if n is not None else None,
            "error": None if self.error is None else str(self.error),
            "source": self.source,
        }

    @classmethod
    def _from_json_dict(cls, d: Dict[str, Any]) -> DraftNode:
        try:
            kind = cls.Type[d["kind"]]
        except KeyError as ex:
            raise ValueError(f"некорректный kind узла: {d.get('kind')!r}") from ex

        n3 = d.get("n3")
        rdf_node: Optional[URIRef | Literal] = None
        if n3 is not None and n3 != "":
            parsed = from_n3(n3)
            if parsed is None or not isinstance(parsed, (URIRef, Literal)):
                raise ValueError(f"ожидался URIRef или Literal после разбора n3: {n3!r}")
            rdf_node = parsed
            if kind == cls.Type.IRI and not isinstance(rdf_node, URIRef):
                raise ValueError("kind=IRI, но n3 не задаёт IRI")
            if kind == cls.Type.LITERAL and not isinstance(rdf_node, Literal):
                raise ValueError("kind=LITERAL, но n3 не задаёт литерал")

        err = d.get("error")
        if err is not None and not isinstance(err, str):
            err = str(err)
        src = d.get("source")
        if src is not None and not isinstance(src, str):
            src = str(src)

        return cls(kind, rdf_node, err, src)


class DraftTriple:
    """Черновой триплет (некоторые ноды могут не иметь значения)."""

    NODE_ROLES = frozenset({"subject", "predicate", "object"})

    class Type(Enum):
        """Возможные типы триплета (в системе можно создать только эти типы)."""
        TYPE = auto()
        OBJECT_PROPERTY = auto()
        DATA_PROPERTY = auto()

    def __init__(self, triple_type: Type, s: DraftNode, p: DraftNode, o: DraftNode):
        self.triple_type = triple_type  # тип триплета
        self.subject = s                # субъект
        self.predicate = p              # предикат
        self.object = o                 # объект

    def get_node(self, role: str) -> DraftNode:
        """Узел по роли: ``subject`` | ``predicate`` | ``object``."""
        if role not in self.NODE_ROLES:
            raise ValueError(f"некорректная роль узла: {role!r}")
        if role == "subject":
            return self.subject
        if role == "predicate":
            return self.predicate
        return self.object

    def is_complete(self) -> bool:
        """Проверяет, является ли триплет полным."""
        return self.subject.is_complete() and self.predicate.is_complete() and self.object.is_complete()

    def get_rdf_triple(self) -> Optional[Tuple[Node, Node, Node]]:
        if not self.is_complete():
            return None

        return (self.subject.get_rdf_node(), self.predicate.get_rdf_node(), self.object.get_rdf_node())

    def _to_json_dict(self) -> Dict[str, Any]:
        return {
            "triple_type": self.triple_type.name,
            "subject": self.subject._to_json_dict(),
            "predicate": self.predicate._to_json_dict(),
            "object": self.object._to_json_dict(),
        }

    @classmethod
    def _from_json_dict(cls, d: Dict[str, Any]) -> DraftTriple:
        try:
            tt = cls.Type[d["triple_type"]]
        except KeyError as ex:
            raise ValueError(f"некорректный triple_type: {d.get('triple_type')!r}") from ex
        return cls(
            tt,
            DraftNode._from_json_dict(d["subject"]),
            DraftNode._from_json_dict(d["predicate"]),
            DraftNode._from_json_dict(d["object"]),
        )


class DraftGraph:
    """Черновой граф (триплеты могут быть неполными)."""

    def __init__(self):
        self.triples: List[DraftTriple] = []

    def add_triple(self, triple: DraftTriple):
        """Добавляет черновой триплет в граф."""
        self.triples.append(triple)

    def is_complete(self) -> bool:
        """Проверяет, является ли граф полным (все триплеты имеют значения)."""
        return all(triple.is_complete() for triple in self.triples)

    def get_rdf_graph(self) -> Graph:
        """Построение реального RDF-графа (из rdflib)."""
        if not self.is_complete():
            return None

        graph = Graph()
        for triple in self.triples:
            graph.add(triple.get_rdf_triple())

        return graph

    # --- сериализация/десериализация ---

    def _to_json_dict(self) -> Dict[str, Any]:
        return {"triples": [t._to_json_dict() for t in self.triples]}

    @classmethod
    def _from_json_dict(cls, data: Dict[str, Any]) -> DraftGraph:
        triples = data.get("triples")
        if not isinstance(triples, list):
            raise ValueError("поле triples должно быть списком")

        g = cls()
        for item in triples:
            if not isinstance(item, dict):
                raise ValueError("элемент triples должен быть объектом")
            g.add_triple(DraftTriple._from_json_dict(item))
        return g

    def save(self, path: Path):
        """Сохраняет черновой граф в UTF-8 JSON-файл."""
        path.write_text(
            json.dumps(self._to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> DraftGraph:
        """Загружает черновой граф из UTF-8 JSON-файла."""
        return cls._from_json_dict(json.loads(path.read_text(encoding="utf-8")))


class EditedGraph:
    """
    Обёртка над неизменяемым :class:`DraftGraph` с учётом правок перед загрузкой в онтологию.

    Исходный граф не модифицируется; правки хранятся отдельно и сериализуются сами по себе.
    """

    def __init__(self, draft: DraftGraph):
        self.draft = draft
        self.excluded: Set[int] = set()
        self.node_overrides: Dict[Tuple[int, str], DraftNode] = {}

    def _triple_index_in_range(self, index: int):
        n = len(self.draft.triples)
        if index < 0 or index >= n:
            raise IndexError(f"Индекс триплета вне диапазона [0, {n}): {index}")

    def exclude_triple(self, index: int):
        """Помечает триплет исходного графа как не подлежащий загрузке в модель."""
        self._triple_index_in_range(index)
        self.excluded.add(index)

    def include_triple(self, index: int):
        """Снимает пометку «не нужен» с триплета исходного графа."""
        self._triple_index_in_range(index)
        self.excluded.discard(index)

    def set_node(self, triple_index: int, role: str, node: DraftNode):
        """
        Задаёт замену узла (s/p/o) для триплета исходного графа.
        Если узел совпадает с исходным, переопределение снимается.
        """
        self._triple_index_in_range(triple_index)
        if role not in DraftTriple.NODE_ROLES:
            raise ValueError(f"Некорректная роль узла: {role!r}")

        key = (triple_index, role)
        original = self.draft.triples[triple_index].get_node(role)
        if node.equals(original):
            self.node_overrides.pop(key, None)
        else:
            self.node_overrides[key] = node

    def build_modified_graph(self) -> DraftGraph:
        """Новый :class:`DraftGraph` — копия исходного с учётом исключений и замен узлов."""
        out = DraftGraph()
        for i, tr in enumerate(self.draft.triples):
            if i in self.excluded:
                continue
            s = self.node_overrides.get((i, "subject"), tr.subject).copy()
            p = self.node_overrides.get((i, "predicate"), tr.predicate).copy()
            o = self.node_overrides.get((i, "object"), tr.object).copy()
            out.add_triple(DraftTriple(tr.triple_type, s, p, o))
        return out

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация только правок (исходный граф не входит в результат)."""
        overrides: List[Dict[str, Any]] = []
        for (ti, role), node in sorted(self.node_overrides.items()):
            overrides.append(
                {"triple_index": ti, "role": role, "node": node._to_json_dict()}
            )
        return {
            "excluded_triple_indices": sorted(self.excluded),
            "node_overrides": overrides,
        }

    @classmethod
    def from_dict(cls, draft: DraftGraph, data: Dict[str, Any]) -> EditedGraph:
        """Восстановление правок по словарю :meth:`to_dict` и ссылке на исходный граф."""
        eg = cls(draft)
        ex = data.get("excluded_triple_indices")
        if ex is not None:
            if not isinstance(ex, (list, tuple)):
                raise ValueError("excluded_triple_indices должен быть списком")
            for i in ex:
                if not isinstance(i, int):
                    raise ValueError("Элемент excluded_triple_indices должен быть int")
                eg.exclude_triple(i)

        ovs = data.get("node_overrides")
        if ovs is not None:
            if not isinstance(ovs, list):
                raise ValueError("node_overrides должен быть списком")
            for item in ovs:
                if not isinstance(item, dict):
                    raise ValueError("Элемент node_overrides должен быть объектом")
                ti = item.get("triple_index")
                role = item.get("role")
                nd = item.get("node")
                if not isinstance(ti, int):
                    raise ValueError("triple_index должен быть int")
                if role not in DraftTriple.NODE_ROLES:
                    raise ValueError(f"Некорректный role: {role!r}")
                if not isinstance(nd, dict):
                    raise ValueError("node должен быть объектом")
                eg.set_node(ti, role, DraftNode._from_json_dict(nd))

        return eg

    def save(self, path: Path):
        """Сохраняет правки в UTF-8 JSON (без исходного графа)."""
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, draft: DraftGraph, edits_path: Path) -> EditedGraph:
        """Загружает правки из UTF-8 JSON и сочетает их с переданным исходным графом."""
        edits_data = None
        if edits_path.exists():
            try:
                edits_data = json.loads(edits_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if edits_data:
            return cls.from_dict(draft, edits_data)
        else:
            return cls(draft)
