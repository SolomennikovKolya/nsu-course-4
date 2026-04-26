from rdflib import Graph
from abc import ABC, abstractmethod
from typing import List

from core.template.field import Field
from core.uddm.model import UDDM
from core.rdf.field_accessor import FieldsAccessor


class BaseTemplateCode(ABC):
    """Базовый класс для кода шаблона. Содержит методы, которые должен переопределить реальный код шаблона."""

    @abstractmethod
    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        """
        Определяет, подходит ли данный документ под этот шаблон.

        Аргументы:
            doc_name (str): Название документа.
            uddm (UDDM): Объект структуры документа, позволяет обращаться к содержимому документа для анализа.

        Возвращает:
            bool: True — если документ должен обрабатываться данным шаблоном, иначе False.

        Пример:
            Можно проверить заголовки, наличие определённых ключевых фраз или просто посмотреть на название документа.
        """
        pass

    @abstractmethod
    def fields(self) -> List[Field]:
        """
        Описывает поля, которые требуется извлечь из документа.

        Возвращает:
            List[Field]: Список объектов Field, каждый из которых содержит описание,
                как извлечь, валидировать и определить релевантность для конкретного поля.

        Пример:
            return [
                Field("organization", "Организация, в которую отправлен документ", Field.Type.LITERAL, ..., ..., ...),
                ...
            ]
        """
        pass

    @abstractmethod
    def build_triples(self, g: Graph, f: FieldsAccessor):
        """
        Построение графа RDF на основе извлечённых значений полей.

        Аргументы:
            g (Graph): Граф RDF, в который будут добавлены триплеты.
            f (FieldsAccessor): Аксессор к извлечённым значениям полей.

        Пример:
        ```
        DOC = URIRef("doc:current")

        student = f.uri("student_name", "onto:Student/")
        course = f.literal("course_number")

        g.add((DOC, RDF.type, URIRef("onto:PracticeApplication")))

        if student:
            g.add((DOC, URIRef("onto:hasStudent"), student))
            g.add((student, RDF.type, URIRef("onto:Student")))

        if course:
            g.add((DOC, URIRef("onto:courseNumber"), course))
        ```
        """
        pass
