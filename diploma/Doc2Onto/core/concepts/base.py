"""
Базовый интерфейс концепта онтологии.

Концепт — это самостоятельный модуль, инкапсулирующий ВСЁ знание о
конкретном концепте онтологии (классе или дататипе): как разобрать сырое
значение, как привести его к канонической форме, какой у него локальный
IRI (если это индивид) и какие триплеты нужно добавить в граф при
регистрации индивида.

Универсальные операции — ``FieldNormalizer.concept(...)`` и
``TemplateGraphBuilder.individual(...)`` — принимают подкласс
:class:`BaseConcept` и работают с любым концептом, не зная про конкретную
реализацию.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Mapping, Optional, Sequence

if TYPE_CHECKING:
    from rdflib import URIRef

    from core.graph.draft_graph import DraftTriple


class ConceptKind(Enum):
    """Вид концепта.

    Attributes:
        CLASS_INDIVIDUAL: Концепт соответствует классу онтологии. При
            регистрации в графе порождает индивид с собственным IRI и
            набором идентифицирующих литералов (например ``:Персона`` →
            IRI + ``:фио``, ``:фамилия``, ``:имя``, ``:отчество``).
        DATATYPE: Концепт описывает значение типа данных. В графе
            существует только как литерал, отдельный индивид не
            создаётся (например ``xsd:date`` — нормализованная
            ISO-строка).
    """
    CLASS_INDIVIDUAL = "class_individual"
    DATATYPE = "datatype"


class ConceptError(ValueError):
    """Концепт не смог разобрать или нормализовать значение.

    Поднимается из :meth:`BaseConcept.parse` (и через него — из
    :meth:`BaseConcept.normalize`), когда сырое значение не соответствует
    предметной форме концепта. Сообщение исключения попадает в UI как
    причина того, что поле не нормализовано.
    """


@dataclass(frozen=True)
class ConceptParts:
    """Структурное представление значения концепта.

    Возвращается из :meth:`BaseConcept.parse`. Содержит каноническую
    строку (она хранится в ``FieldResult.value_normalized`` поля) и
    словарь именованных «частей», специфичных для конкретного концепта
    (фамилия/имя/отчество для ``Person``, день/месяц/год для ``Date``,
    локал/домен для ``Email`` и т. п.).

    Каноническая форма обязана быть детерминированной — два
    эквивалентных по смыслу входа (``"Ивановой Анне"`` и ``"Иванова
    Анна"``) должны дать одну и ту же ``canonical``, иначе индивиды в
    графе не схлопнутся.

    Attributes:
        canonical: Каноническая строка значения (то, что пишется в
            ``value_normalized`` и используется при сборке графа).
        parts: Дополнительные именованные значения. Состав ключей — на
            усмотрение конкретного концепта; рекомендуется фиксировать
            набор ключей в его docstring. Может быть пустым, если
            канонической строки достаточно.
    """
    canonical: str
    parts: Mapping[str, Optional[str]] = field(default_factory=dict)

    def get(self, key: str) -> Optional[str]:
        """Удобный доступ к именованной части (None, если части нет)."""
        return self.parts.get(key)


class BaseConcept(ABC):
    """Базовый класс для всех концептов онтологии.

    Подклассы — stateless. Все методы — class-методы; экземпляры не
    создаются (``BaseConcept()`` не вызывается). Подкласс ОБЯЗАН задать
    атрибуты :attr:`name`, :attr:`kind`, для ``CLASS_INDIVIDUAL`` ещё и
    :attr:`onto_class_local`, и реализовать :meth:`parse`. Для концептов
    вида ``CLASS_INDIVIDUAL`` ОБЯЗАН также реализовать :meth:`iri_local`
    (стратегия хеширования специфична для концепта). Остальные методы
    имеют разумные дефолты.

    Жизненный цикл значения::

        raw_value (str) ── parse() ──▶ ConceptParts
                                        │
                                        ├─▶ ConceptParts.canonical          (FieldResult.value_normalized)
                                        ├─▶ iri_local(parts)                (CLASS_INDIVIDUAL)
                                        └─▶ build_triples(parts, subject)   (CLASS_INDIVIDUAL)
    """

    # --- Атрибуты класса (задаются подклассом) ----------------------------

    name: ClassVar[str]
    """Уникальное имя концепта (snake_case): ``"person"``, ``"date"``,
    ``"group"``. Используется как ключ в реестре концептов и как
    диагностический идентификатор в логах/ошибках."""

    kind: ClassVar[ConceptKind]
    """Вид концепта (см. :class:`ConceptKind`)."""

    onto_class_local: ClassVar[Optional[str]] = None
    """Локальное имя класса в онтологии (без namespace), например
    ``"Персона"``. Для ``DATATYPE``-концептов остаётся ``None``."""

    # --- Парсинг и нормализация -------------------------------------------

    @classmethod
    @abstractmethod
    def parse(cls, raw: str) -> ConceptParts:
        """Разобрать сырое значение в структурированную форму.

        Должен быть детерминированным и идемпотентным относительно
        канонического представления (``parse(parse(x).canonical)`` даёт
        ``ConceptParts`` с тем же ``canonical``).

        Raises:
            ConceptError: значение не распознано или не приводимо к
                канонической форме.
        """

    @classmethod
    def normalize(cls, raw: str) -> str:
        """Каноническая строка — краткая обёртка над :meth:`parse`.

        Raises:
            ConceptError: значение не распознано.
        """
        return cls.parse(raw).canonical

    @classmethod
    def is_valid(cls, raw: str) -> bool:
        """Проверка без побочных эффектов: можно ли разобрать значение."""
        try:
            cls.parse(raw)
        except ConceptError:
            return False
        return True

    # --- Идентичность (только для CLASS_INDIVIDUAL) -----------------------

    @classmethod
    def iri_local(cls, parts: ConceptParts) -> str:
        """Локальное имя IRI индивида для данного значения.

        Подкласс ``CLASS_INDIVIDUAL`` обязан переопределить (стратегия
        хеширования специфична: ``Персона_<sha1[:12]>``,
        ``Группа_22204`` без хеша, ``Направление_09_03_01`` с заменой
        точек на подчёркивания, и т. п.). Дефолт здесь сознательно
        отсутствует, чтобы случайно не получить «средний» IRI.

        Raises:
            NotImplementedError: концепт является ``DATATYPE`` —
                индивидов не порождает; либо подкласс не переопределил
                метод.
        """
        if cls.kind != ConceptKind.CLASS_INDIVIDUAL:
            raise NotImplementedError(
                f"Концепт '{cls.name}' имеет kind={cls.kind.value}; "
                f"iri_local применим только к CLASS_INDIVIDUAL."
            )
        raise NotImplementedError(
            f"Концепт '{cls.name}' (CLASS_INDIVIDUAL) обязан переопределить iri_local()."
        )

    # --- Триплеты (только для CLASS_INDIVIDUAL) ---------------------------

    @classmethod
    def build_triples(
        cls,
        parts: ConceptParts,
        *,
        subject_iri: "URIRef",
    ) -> Sequence["DraftTriple"]:
        """Идентифицирующие триплеты индивида данного концепта.

        Возвращает триплеты помимо ``rdf:type`` — этот добавляет билдер.
        Например :class:`PersonConcept` выдаёт ``:фио``, ``:фамилия``,
        ``:имя``, ``:отчество``, а :class:`GroupConcept` —
        ``:номерГруппы``.

        Дефолт — пустая последовательность. Подходит для концептов, у
        которых индивид определяется только своим IRI и литералов в
        графе оставлять не нужно (актуально для перечислений типа
        ``:Должность_Доцент``).

        Args:
            parts: Структурированное значение из :meth:`parse`.
            subject_iri: IRI индивида (полученный из ``iri_local``,
                префиксованный namespace-ом проекта).

        Returns:
            Последовательность :class:`DraftTriple` для добавления в
            граф.
        """
        return ()


__all__ = [
    "BaseConcept",
    "ConceptError",
    "ConceptKind",
    "ConceptParts",
]
