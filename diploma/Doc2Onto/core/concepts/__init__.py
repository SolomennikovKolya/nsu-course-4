"""
Концепты онтологии.

Каждый концепт (Персона, Группа, Дата, Организация, Должность, …) живёт
в своём модуле и предоставляет единый интерфейс :class:`BaseConcept`:
парсинг, нормализация, локальное имя IRI и набор идентифицирующих
триплетов. См. :mod:`core.concepts.base` для подробностей контракта.

Реализованные концепты:
    * Простые/основные: :class:`PersonConcept`, :class:`OrganizationConcept`,
      :class:`GroupConcept`, :class:`DirectionConcept`, :class:`ProfileConcept`,
      :class:`ThesisConcept`.
    * Перечисления: :class:`PositionConcept`, :class:`DegreeConcept`,
      :class:`TitleConcept`, :class:`GradeConcept`.
    * Datatype-подобные с собственным IRI:
      :class:`EmailConcept`, :class:`TelephoneConcept`.
    * Чистый datatype: :class:`DateConcept` (литерал ``xsd:date``,
      без индивида).
"""
from core.concepts.base import (
    BaseConcept,
    ConceptError,
    ConceptKind,
    ConceptParts,
)
from core.concepts.date import DateConcept
from core.concepts.degree import DegreeConcept
from core.concepts.direction import DirectionConcept
from core.concepts.email import EmailConcept
from core.concepts.grade import GradeConcept
from core.concepts.group import GroupConcept
from core.concepts.organization import OrganizationConcept
from core.concepts.person import PersonConcept
from core.concepts.position import PositionConcept
from core.concepts.practice import PracticeConcept
from core.concepts.profile import ProfileConcept
from core.concepts.telephone import TelephoneConcept
from core.concepts.thesis import ThesisConcept
from core.concepts.title import TitleConcept

__all__ = [
    "BaseConcept",
    "ConceptError",
    "ConceptKind",
    "ConceptParts",
    "DateConcept",
    "DegreeConcept",
    "DirectionConcept",
    "EmailConcept",
    "GradeConcept",
    "GroupConcept",
    "OrganizationConcept",
    "PersonConcept",
    "PositionConcept",
    "PracticeConcept",
    "ProfileConcept",
    "TelephoneConcept",
    "ThesisConcept",
    "TitleConcept",
]
