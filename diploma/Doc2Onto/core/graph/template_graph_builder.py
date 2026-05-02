from rdflib import Namespace
from rdflib import URIRef, Literal
from typing import Optional, Dict, Any

from app.settings import SUBJECT_NAMESPACE_IRI
from core.graph.draft_graph import DraftNode, DraftTriple, DraftGraph
from core.graph.value_transformer import ValueTransformFunc
from core.graph.rdflib_draft_outer import OUTER


class DomainNamespace:
    """
    Пространство имен предметной области. Позволяет легко создавать IRI с префиксом пространства имен.
    Возвращает специальную обёртку над URIRef для работы в шаблоне.
    """

    def __init__(self, ontology_iri: str):
        self._ontology_iri = ontology_iri
        self._namespace = Namespace(ontology_iri)

    def get_ontology_iri(self) -> str:
        return self._ontology_iri

    def _to_draft_node(self, local_name: str) -> DraftNode:
        uri = self._namespace[local_name]
        return DraftNode(None, DraftNode.Type.IRI, uri, None)

    def __getitem__(self, local_name: str) -> DraftNode:
        return self._to_draft_node(local_name)

    def __getattr__(self, local_name: str) -> DraftNode:
        # Пропускаем служебные python-атрибуты.
        if local_name.startswith("__"):
            raise AttributeError(local_name)
        return self._to_draft_node(local_name)


"""
Пространство имен предметной области.
С помощью него можно получить класс, объектное или дата-свойство онтологии.
Примеры: `ONTO.Студент`, `ONTO.имеетРуководителя`, `ONTO.имеетИмя`
"""
ONTO = DomainNamespace(SUBJECT_NAMESPACE_IRI)
_RDFLIB_ONTO = Namespace(SUBJECT_NAMESPACE_IRI)


class ValueProxy:
    """
    Прокси для значения поля. Используется для fluent API.
    Позволяет писать цепочки вида:
    ```
    student_email_domain = b.field("student_email").\\
        transform(ValueTransformer.email, "domain").\\
        literal()
    ```
    """

    def __init__(self, field_name: str, field_value: Optional[str]):
        self._source_field_name: str = field_name              # название поля, от которого было получено значение
        self._source_field_value: Optional[str] = field_value  # исходное значение поля
        self._transformed_value: Optional[str] = None          # преобразованное значение поля
        self._error: Optional[str] = None                      # ошибка в цепочке

    def _transform_called(self) -> bool:
        return self._transformed_value is not None or self._error is not None

    def _get_value(self) -> Optional[str]:
        return self._transformed_value or self._source_field_value

    def transform(self, fn: ValueTransformFunc, key: str) -> "ValueProxy":
        """
        Преобразование значения поля в данные, пригодные для использования в IRI.

        Аргументы:
            fn: ValueTransformFunc - вспомогательная функция, которая принимает значение поля и возвращает словарь данных.
            key: str - ключ, по которому нужно получить значение из словаря результата преобразования.
        """
        if self._error is not None:
            return self

        value = self._get_value()
        if value is None:
            self._error = "Значение поля отсутствует; Невозможно применить transform к None"
            return self

        try:
            data = fn(value)
            if key not in data:
                self._error = f"Ключ {key} не найден в результате преобразования"
            else:
                self._transformed_value = data.get(key)
        except Exception as ex:
            self._error = str(ex)

        return self

    def iri(self) -> DraftNode:
        """
        Построение IRI на основе значения поля. 
        Является конечной операцией в цепочке.
        """
        def node(value: Optional[URIRef], error: Optional[str]) -> DraftNode:
            return DraftNode(self._source_field_name, DraftNode.Type.IRI, value, error)

        if self._error is not None:
            return node(None, self._error)

        value = self._get_value()
        if value is None:
            error = "Значение поля отсутствует; Невозможно построить IRI из None"
            return node(None, error)

        return node(_RDFLIB_ONTO[value], None)

    def literal(self, datatype: Optional[DraftNode] = None) -> DraftNode:
        """
        Построение Literal на основе значения поля с учётом типа. 
        Является конечной операцией в цепочке.
        """
        def node(value: Optional[Literal], error: Optional[str]) -> DraftNode:
            return DraftNode(self._source_field_name, DraftNode.Type.LITERAL, value, error)

        if self._error is not None:
            return node(None, self._error)

        value = self._get_value()
        if value is None:
            error = "Значение поля отсутствует; Невозможно построить Literal из None"
            return node(None, error)

        dt_iri = datatype._get_rdf_node() if datatype is not None else OUTER.XSD.string._get_rdf_node()
        if not isinstance(dt_iri, URIRef):
            error = "Неверный тип datatype: ожидается именованная сущность (имеющая IRI)"
            return node(None, error)

        return node(Literal(value, datatype=dt_iri), None)


class NoneValueProxy(ValueProxy):
    """Заглушка на случай, если поле не существует в шаблоне."""

    def __init__(self, field_name: str):
        super().__init__(field_name, None)
        self.ERROR = f"Поле {field_name} не существует в шаблоне"

    def transform(self, fn: ValueTransformFunc, key: str) -> "NoneValueProxy":
        return self

    def iri(self) -> DraftNode:
        return DraftNode(None, DraftNode.Type.IRI, None, self.ERROR)

    def literal(self, datatype: Optional[DraftNode] = None) -> DraftNode:
        return DraftNode(None, DraftNode.Type.LITERAL, None, self.ERROR)


class TemplateGraphBuilder:
    """
    Билдер для построения RDF-графа внутри кода шаблона.
    Является сужающей обёрткой над rdflib специализированной для предметной области.

    Предоставляет:
    - Методы для создания IRI и Literal на основе полей шаблона.
    - Методы для добавления триплетов в граф.

    Приемущества:
    - Повышение детерминизма за счет ограничения выразительности (по сравнению с чистой rdflib)
    - Упрощение автоматической генерации шаблонов
    - Инкапсуляция типизации и построения IRI
    """

    def __init__(self, field_values: Dict[str, str]):
        self._field_values = field_values
        self._draft_graph: DraftGraph = DraftGraph()

    def _get_draft_graph(self) -> DraftGraph:
        return self._draft_graph

    # ----- доступ к полям шаблона и константным литералам -----

    def field(self, field_name: str) -> ValueProxy:
        """
        Получение прокси для значения поля (lazy transformation wrapper над значением поля). 
        Используется для построения цепочек в стиле fluent API.

        Примеры:
        ```
        student = b.field("student_name").transform(ValueTransformer.person, "hash").iri()
        course = b.field("course_number").literal(OUTER.XSD.integer)
        email_domain = b.field("student_email").transform(ValueTransformer.email, "domain").literal()
        ```
        """
        if field_name not in self._field_values:
            return NoneValueProxy(field_name)

        value = self._field_values.get(field_name)
        return ValueProxy(field_name, value)

    def const_literal(self, value: Any, datatype: Optional[DraftNode] = None) -> DraftNode:
        """Построение Literal на основе значения (не связано ни с каким полем шаблона)."""
        dt_iri = datatype._get_rdf_node() if datatype is not None else None
        if not isinstance(dt_iri, URIRef):
            dt_iri = OUTER.XSD.string._get_rdf_node()

        return DraftNode(None, DraftNode.Type.LITERAL, Literal(value, datatype=dt_iri), None)

    # ----- добавление триплетов -----

    def add_type(self, s: DraftNode, c: DraftNode):
        """Добавляет триплет вида: (экземпляр, RDF.type, класс)."""
        self._add_triple(DraftTriple.Type.TYPE, s, OUTER.RDF.type, c)

    def add_object_property(self, s: DraftNode, p: DraftNode, o: DraftNode):
        """Добавляет триплет вида: (экземпляр, объектное свойство, экземпляр)."""
        self._add_triple(DraftTriple.Type.OBJECT_PROPERTY, s, p, o)

    def add_data_property(self, s: DraftNode, p: DraftNode, l: DraftNode):
        """Добавляет триплет вида: (экземпляр, дата-свойство, литерал)."""
        self._add_triple(DraftTriple.Type.DATA_PROPERTY, s, p, l)

    def _add_triple(self, triple_type: DraftTriple.Type, s: DraftNode, p: DraftNode, o: DraftNode):
        self._draft_graph.add_triple(DraftTriple(triple_type, s, p, o))
