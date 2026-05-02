from typing import Optional, List, Tuple
from rdflib import URIRef, Literal, Graph, Node
from enum import Enum, auto


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
        self._type = node_type  # тип узла
        self._rdf_node = node   # значение узла (node != None <=> error == None)
        self._error = error     # ошибка, поясняющая причину отсутствия значения
        self._source = source   # источник (название поля шаблона или None, если значение не связано с каким-либо полем)

    def is_ok(self) -> bool:
        """Проверяет, является ли узел полным (содержащим значение)."""
        return self._rdf_node is not None

    def is_iri(self) -> bool:
        """Проверяет, является ли узел IRI."""
        return self._type == DraftNode.Type.IRI

    def is_literal(self) -> bool:
        """Проверяет, является ли узел литералом."""
        return self._type == DraftNode.Type.LITERAL

    def _get_rdf_node(self) -> Optional[URIRef | Literal]:
        return self._rdf_node


class DraftTriple:
    """Черновой триплет (некоторые ноды могут не иметь значения)."""

    class Type(Enum):
        """Возможные типы триплета (в системе можно создать только эти типы)."""
        TYPE = auto()
        OBJECT_PROPERTY = auto()
        DATA_PROPERTY = auto()

    def __init__(self, triple_type: Type, s: DraftNode, p: DraftNode, o: DraftNode):
        self._triple_type = triple_type  # тип триплета
        self._subject = s                # субъект
        self._predicate = p              # предикат
        self._object = o                 # объект

    def is_complete(self) -> bool:
        """Проверяет, является ли триплет полным."""
        return self._subject.is_ok() and self._predicate.is_ok() and self._object.is_ok()

    def _get_rdf_triple(self) -> Optional[Tuple[Node, Node, Node]]:
        if not self.is_complete():
            return None
        return (self._subject._get_rdf_node(), self._predicate._get_rdf_node(), self._object._get_rdf_node())


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
            rdf_triple = triple._get_rdf_triple()
            if rdf_triple is not None:
                graph.add(rdf_triple)

        return graph
