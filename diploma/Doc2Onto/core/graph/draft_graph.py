from __future__ import annotations

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    def save(self, path: Path) -> None:
        """Сохраняет черновой граф в UTF-8 JSON-файл."""
        path.write_text(
            json.dumps(self._to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> DraftGraph:
        """Загружает черновой граф из UTF-8 JSON-файла."""
        return cls._from_json_dict(json.loads(path.read_text(encoding="utf-8")))
