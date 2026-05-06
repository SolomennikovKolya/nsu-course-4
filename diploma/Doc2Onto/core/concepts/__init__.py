"""
Концепты онтологии.

Каждый концепт (Персона, Группа, Дата, Организация, Должность, …) живёт
в своём модуле и предоставляет единый интерфейс :class:`BaseConcept`:
парсинг, нормализация, локальное имя IRI и набор идентифицирующих
триплетов. См. :mod:`core.concepts.base` для подробностей контракта.

Реализованные концепты:
    * :class:`GroupConcept` — :Группа (CLASS_INDIVIDUAL без хеша).
    * :class:`DateConcept` — xsd:date (DATATYPE).
    * :class:`PersonConcept` — :Персона (CLASS_INDIVIDUAL с морфологией
      ФИО и хешированием sort-key).
"""
from core.concepts.base import (
    BaseConcept,
    ConceptError,
    ConceptKind,
    ConceptParts,
)
from core.concepts.date import DateConcept
from core.concepts.group import GroupConcept
from core.concepts.person import PersonConcept

__all__ = [
    "BaseConcept",
    "ConceptError",
    "ConceptKind",
    "ConceptParts",
    "DateConcept",
    "GroupConcept",
    "PersonConcept",
]
