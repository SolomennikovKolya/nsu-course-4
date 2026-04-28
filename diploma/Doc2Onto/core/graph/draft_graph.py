from typing import Optional, List, Tuple
from rdflib import URIRef, Literal, Graph, Node
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
        source_field_name: str,
        node_type: Type,
        node: Optional[URIRef | Literal],
        error: Optional[Exception] = None
    ):
        self._source_field_name = source_field_name  # название поля, от которого было получено значение
        self._node_type = node_type                  # тип узла
        self._node = node                            # значение узла (node != None <=> error == None)
        self._error = error                          # ошибка, поясняющая причину отсутствия значения

    def is_ok(self):
        return self._node is not None

    def get_rdf_node(self) -> Optional[URIRef | Literal]:
        return self._node


class DraftTriple:
    """Черновой триплет (некоторые ноды могут не иметь значения)."""

    def __init__(self, s: DraftNode, p: DraftNode, o: DraftNode):
        self._subject = s
        self._predicate = p
        self._object = o

    def is_complete(self) -> bool:
        """Проверяет, является ли триплет полным."""
        return self._subject.is_ok() and self._predicate.is_ok() and self._object.is_ok()

    def get_rdf_triple(self) -> Optional[Tuple[Node, Node, Node]]:
        if not self.is_complete():
            return None
        return (self._subject.get_rdf_node(), self._predicate.get_rdf_node(), self._object.get_rdf_node())


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
            rdf_triple = triple.get_rdf_triple()
            if rdf_triple is not None:
                graph.add(rdf_triple)

        return graph
