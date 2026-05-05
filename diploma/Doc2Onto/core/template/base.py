from abc import ABC, abstractmethod
from typing import List

from core.fields.field import Field
from core.uddm.model import UDDM
from core.graph.template_graph_builder import TemplateGraphBuilder


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
        """
        pass

    @abstractmethod
    def fields(self) -> List[Field]:
        """
        Описывает поля, которые требуется извлечь из документа.

        Возвращает:
            List[Field]: Список объектов Field, каждый из которых содержит описание,
                как выбрать, извлечь и валидировать конкретное поле.
                Описание поля должно быть осмысленным и исчерпывающим.
        """
        pass

    @abstractmethod
    def build(self, b: TemplateGraphBuilder):
        """
        Построение графа триплетов на основе извлечённых значений полей.

        Аргументы:
            b (TemplateGraphBuilder): Билдер для построения графа.
        """
        pass
