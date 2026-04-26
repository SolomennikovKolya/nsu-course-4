from rdflib import Graph, Namespace
from rdflib.namespace import RDF
from rdflib import URIRef, Literal, XSD
from typing import Optional, Dict
from enum import Enum

from app.settings import SUBJECT_NAMESPACE_IRI


"""
Пространство имен предметной области.

С помощью этого пространства можно:
1. получить класс, объектное или дата-свойство онтологии.
2. создать константный IRI ресурса (лучше это делать через метод get_iri билдера).
"""
ONTO = Namespace(SUBJECT_NAMESPACE_IRI)


class XSDType(Enum):
    """Типы данных RDF. Используются для построения Literal с учётом типа."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"

    @property
    def uri(self) -> URIRef:
        return {
            self.STRING: XSD.string,
            self.INTEGER: XSD.integer,
            self.FLOAT: XSD.float,
            self.DATE: XSD.date,
        }[self]

    @property
    def py_type(self) -> type:
        return {
            self.STRING: str,
            self.INTEGER: int,
            self.FLOAT: float,
            self.DATE: str,
        }[self]


class TemplateGraphBuilder:
    """
    Билдер для построения RDF-графа внутри кода шаблона.
    Является сужающей обёрткой над rdflib специализированной для предметной области.

    Предоставляет:
    - Методы для создания IRI и Literal на основе полей шаблона.
    - Методы для добавления триплетов в граф.

    Приемущества:
    - Повышение детерминизма за счет ограничения выразительности
    - Упрощение автоматической генерации шаблонов
    - Инкапсуляция типизации и построения IRI
    """

    def __init__(self, graph: Graph, field_values: Dict[str, str]):
        self._graph = graph
        self._field_values = field_values

    def get_graph(self) -> Graph:
        """
        Получение графа RDF. 

        Важно: 
        - Для большинства случаев получение прямого доступа к графу излишне.
        - Используется исключительно для поддержки всех операций над графом через rdflib,
          чтобы расширить возможности и гибкость системы.
        - При генерации шаблона через LLM этот метод не используется.
        """
        return self._graph

    def _value(self, name: str) -> Optional[str]:
        return self._field_values.get(name, None)

    # ----- построение IRI и Literal -----

    def iri(self, value: Optional[str]) -> Optional[URIRef]:
        """Создает IRI ресурса с префиксом предметной области (ONTO)."""
        if value is None:
            return None

        return ONTO[value]

    def literal(self, value: Optional[str], xsd_type: XSDType = XSDType.STRING) -> Optional[Literal]:
        """Создает Literal с определённым типом (по умолчанию строковым)."""
        if value is None:
            return None

        try:
            value = xsd_type.py_type(value)
        except Exception:
            return None

        return Literal(value, datatype=xsd_type.uri)

    # def field_iri(self, field_name: str) -> Optional[URIRef]:
    #     val = self._value(field_name)
    #     if val is None:
    #         return None

    #     return self.const_iri(val)

    # def field_literal(self, field_name: str, xsd_type: XSDType = XSDType.STRING) -> Optional[Literal]:
    #     val = self._value(field_name)
    #     if val is None:
    #         return None

    #     return self.const_literal(val, xsd_type)

    # ----- добавление триплетов -----

    def _add_triple(self, subject: Optional[URIRef], predicate: Optional[URIRef], object: Optional[URIRef | Literal]):
        if subject is not None and predicate is not None and object is not None:
            self._graph.add((subject, predicate, object))

    def add_type(self, subject: Optional[URIRef], cls: Optional[URIRef]):
        """Добавляет триплет, задающий тип субъекта: (subject, RDF.type, cls)."""
        self._add_triple(subject, RDF.type, cls)

    def add_object_property(self, subject: Optional[URIRef], predicate: Optional[URIRef], object: Optional[URIRef | Literal]):
        """Добавляет триплет, задающий объектное свойство субъекта: (subject, predicate, object)."""
        self._add_triple(subject, predicate, object)

    def add_data_property(self, subject: Optional[URIRef], predicate: Optional[URIRef], literal: Optional[Literal]):
        """Добавляет триплет, задающий дата-свойство субъекта: (subject, predicate, literal)."""
        self._add_triple(subject, predicate, literal)
