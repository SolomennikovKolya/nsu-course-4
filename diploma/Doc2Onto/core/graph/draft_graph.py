from typing import Optional, List
from rdflib import URIRef, Literal, Graph
from enum import Enum


class DraftNode:
    """Черновой узел графа (содержит дополнительные метаданные)."""

    class Type(Enum):
        """
        Тип узла триплета. Либо IRI, либо Literal, т.к. 
        построение триплетов в шаблоне не требует других типов.
        """
        IRI = "iri"
        LITERAL = "literal"

    def __init__(
        self,
        value: Optional[URIRef | Literal],
        node_type: Type,
        error: Optional[Exception] = None
    ):
        self.value = value
        self.type = node_type
        self.error = error

    def is_ok(self):
        return self.value is not None and self.error is None


class DraftTriple:
    """Черновой триплет (некоторые ноды могут не иметь значения)."""

    def __init__(self, s: DraftNode, p: DraftNode, o: DraftNode):
        self.subject = s
        self.predicate = p
        self.object = o

    def is_complete(self) -> bool:
        """Проверяет, является ли триплет полным."""
        return self.subject is not None and self.predicate is not None and self.object is not None

    def __repr__(self):
        status = "OK" if self.is_complete() else "PARTIAL"
        return f"<DraftTriple {self.subject} {self.predicate} {self.object} [{status}]>"


class DraftGraph:
    """Черновой граф (триплеты могут быть неполными)."""

    def __init__(self):
        self._triples: List[DraftTriple] = []

    def add_triple(self, triple: DraftTriple):
        """Добавляет черновой триплет в граф."""
        self._triples.append(triple)

    def build_graph(self) -> Graph:
        """Построение реального RDF-графа (из rdflib)."""
        graph = Graph()
        for triple in self._triples:
            if triple.is_complete():
                graph.add(triple)

        return graph

    def __repr__(self):
        rep = f"<DraftGraph {len(self._triples)} triples>"
        for triple in self._triples:
            rep += f"\n{triple}"
        return rep
