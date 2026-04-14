from rdflib import Graph, Namespace, URIRef, Literal, RDF
from pathlib import Path

from app.settings import ONTOLOGY_PATH


class OntologyRepository:
    """Репозиторий для управления онтологией."""

    def __init__(self, ontology_path: Path = ONTOLOGY_PATH):
        self.ontology_path = ontology_path
        self.graph = Graph()
        self.NS = Namespace("http://doc2onto.org/ontology#")

        if self.ontology_path.exists():
            self.graph.parse(self.ontology_path, format="turtle")

    def save(self):
        self.graph.serialize(self.ontology_path, format="turtle")

    def add_triple(self, s: URIRef, p: URIRef, o: URIRef | Literal):
        self.graph.add((s, p, o))

    def add_individual(self, name: str, class_name: str) -> URIRef:
        subject = URIRef(self.NS[name])
        cls = URIRef(self.NS[class_name])

        self.graph.add((subject, RDF.type, cls))
        return subject

    def add_literal(self, subject: URIRef, predicate: str, value: str):
        pred = URIRef(self.NS[predicate])
        self.graph.add((subject, pred, Literal(value)))

    def query_all(self):
        return list(self.graph)
