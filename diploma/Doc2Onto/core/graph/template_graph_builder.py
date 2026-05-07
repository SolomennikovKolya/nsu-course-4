"""
Билдер RDF-графа для использования внутри кода шаблона.

Сужающая обёртка над rdflib, специализированная под предметную область.
Все знания, специфичные для конкретного концепта (как парсить значение,
как считать IRI, какие литералы добавлять при регистрации индивида),
живут в подклассах :class:`BaseConcept`. Билдер — тонкая прослойка,
которая:

  * читает значение поля из ``field_values`` (уже нормализованное стадией
    Extractor → ``value_normalized``);
  * применяет к нему концепт (``parse`` → ``iri_local`` → ``build_triples``);
  * добавляет результат в граф.

Универсальные методы:
    * :meth:`TemplateGraphBuilder.individual` — создать индивид по
      полю + концепту-``CLASS_INDIVIDUAL`` (Персона, Группа, Организация,
      Профиль, перечисления и т. п.). Опциональный ``role`` добавляет
      второй ``rdf:type``.
    * :meth:`TemplateGraphBuilder.literal` — создать типизированный
      литерал по полю + концепту-``DATATYPE`` (Дата, Email, Телефон).

Композитные хелперы (не вписываются в простую парадигму одно-поле→концепт):
    * :meth:`TemplateGraphBuilder.direction` — направление подготовки с
      опциональным литералом названия.
    * :meth:`TemplateGraphBuilder.thesis` — ВКР: либо от темы, либо
      хеш от IRI студента.
    * :meth:`TemplateGraphBuilder.practice` — Практика: composite IRI
      от тройки (студент, вид, год) + identifying-связи.
"""
from typing import Any, Dict, Optional, Type

from rdflib import Literal, Namespace, URIRef

from app.settings import SUBJECT_NAMESPACE_IRI
from core.concepts._hash import short_sha1
from core.concepts.base import BaseConcept, ConceptError, ConceptKind, ConceptParts
from core.concepts.date import DateConcept
from core.concepts.practice import PracticeConcept
from core.concepts.thesis import ThesisConcept
from core.graph.draft_graph import DraftGraph, DraftNode, DraftTriple
from core.graph.rdflib_draft_outer import OUTER


class DomainNamespace:
    """
    Пространство имён предметной области. Возвращает обёртку над URIRef
    для использования в шаблоне (``ONTO.Студент``, ``ONTO.имеетВКР``).
    """

    def __init__(self, ontology_iri: str):
        self._ontology_iri = ontology_iri
        self._namespace = Namespace(ontology_iri)

    def get_ontology_iri(self) -> str:
        return self._ontology_iri

    def _to_draft_node(self, local_name: str) -> DraftNode:
        uri = self._namespace[local_name]
        return DraftNode(DraftNode.Type.IRI, uri, None, None)

    def __getitem__(self, local_name: str) -> DraftNode:
        return self._to_draft_node(local_name)

    def __getattr__(self, local_name: str) -> DraftNode:
        if local_name.startswith("__"):
            raise AttributeError(local_name)
        return self._to_draft_node(local_name)


ONTO = DomainNamespace(SUBJECT_NAMESPACE_IRI)
"""Пространство имён онтологии: ``ONTO.Класс`` / ``ONTO.свойство``."""

_RDFLIB_ONTO = Namespace(SUBJECT_NAMESPACE_IRI)


class ValueProxy:
    """
    Прокси значения поля для fluent API.

    Позволяет писать:
        b.field("student_email").part(EmailConcept, "domain").literal()

    :meth:`part` применяет :class:`BaseConcept` к значению и достаёт
        нужный ключ (``parts.<key>`` или ``canonical``); 
    :meth:`iri` / :meth:`literal` — терминаторы цепочки.
    """

    def __init__(self, field_name: str, field_value: Optional[str]):
        self._source_field_name: str = field_name
        self._source_field_value: Optional[str] = field_value
        self._transformed_value: Optional[str] = None
        self._error: Optional[str] = None

    def _transform_called(self) -> bool:
        return self._transformed_value is not None or self._error is not None

    def _get_value(self) -> Optional[str]:
        return self._transformed_value or self._source_field_value

    def part(self, concept_cls: Type[BaseConcept], key: str = "canonical") -> "ValueProxy":
        """Применить концепт к значению и взять часть из :class:`ConceptParts`.

        Args:
            concept_cls: Подкласс :class:`BaseConcept`.
            key: Имя части (``"canonical"`` или ключ из ``parts``,
                например ``"domain"`` для :class:`EmailConcept` или
                ``"year"`` для :class:`DateConcept`).
        """
        if self._error is not None:
            return self

        value = self._get_value()
        if value is None:
            self._error = "Значение поля отсутствует; невозможно применить part к None"
            return self

        try:
            parts = concept_cls.parse(value)
        except ConceptError as ex:
            self._error = str(ex)
            return self
        except Exception as ex:  # noqa: BLE001
            self._error = f"{concept_cls.name}: {ex}"
            return self

        if key == "canonical":
            self._transformed_value = parts.canonical
        else:
            v = parts.get(key)
            if v is None:
                self._error = f"Часть '{key}' отсутствует в результате {concept_cls.name}.parse"
            else:
                self._transformed_value = v

        return self

    def iri(self) -> DraftNode:
        """Терминатор: построить IRI из текущего значения."""
        def node(value: Optional[URIRef], error: Optional[str]) -> DraftNode:
            return DraftNode(DraftNode.Type.IRI, value, error, self._source_field_name)

        if self._error is not None:
            return node(None, self._error)
        value = self._get_value()
        if value is None:
            return node(None, "Значение поля отсутствует; невозможно построить IRI из None")
        return node(_RDFLIB_ONTO[value], None)

    def literal(self, datatype: Optional[DraftNode] = None) -> DraftNode:
        """Терминатор: построить типизированный Literal из текущего значения.

        Никаких автоматических преобразований формата не делает. Если
        нужен ``xsd:date`` — значение должно прийти сюда уже в ISO-форме
        (либо нормализатор поля, либо явный ``.part(DateConcept, "canonical")``
        перед терминатором).
        """
        def node(value: Optional[Literal], error: Optional[str]) -> DraftNode:
            return DraftNode(DraftNode.Type.LITERAL, value, error, self._source_field_name)

        if self._error is not None:
            return node(None, self._error)
        value = self._get_value()
        if value is None:
            return node(None, "Значение поля отсутствует; невозможно построить Literal из None")

        dt_iri = datatype.get_rdf_node() if datatype is not None else OUTER.XSD.string.get_rdf_node()
        if not isinstance(dt_iri, URIRef):
            return node(None, "Неверный тип datatype: ожидается именованная сущность (имеющая IRI)")

        return node(Literal(value, datatype=dt_iri), None)


class NoneValueProxy(ValueProxy):
    """Заглушка на случай отсутствия поля в шаблоне."""

    def __init__(self, field_name: str):
        super().__init__(field_name, None)
        self.ERROR = f"Поле {field_name} не существует в шаблоне"

    def part(self, concept_cls: Type[BaseConcept], key: str = "canonical") -> "NoneValueProxy":
        return self

    def iri(self) -> DraftNode:
        return DraftNode(DraftNode.Type.IRI, None, self.ERROR, None)

    def literal(self, datatype: Optional[DraftNode] = None) -> DraftNode:
        return DraftNode(DraftNode.Type.LITERAL, None, self.ERROR, None)


class TemplateGraphBuilder:
    """
    Билдер RDF-графа для шаблона.

    См. подробности в module-level docstring.
    """

    def __init__(self, field_values: Dict[str, str]):
        self._field_values = field_values
        self._draft_graph: DraftGraph = DraftGraph()

    def _get_draft_graph(self) -> DraftGraph:
        return self._draft_graph

    # ----- доступ к значениям полей и константам -----

    def field(self, field_name: str) -> ValueProxy:
        """Прокси значения поля — для fluent API. См. :class:`ValueProxy`."""
        if field_name not in self._field_values:
            return NoneValueProxy(field_name)
        return ValueProxy(field_name, self._field_values.get(field_name))

    def const_literal(self, value: Any, datatype: Optional[DraftNode] = None) -> DraftNode:
        """Литерал с произвольным значением, не привязанный к полю."""
        dt_iri = datatype.get_rdf_node() if datatype is not None else None
        if not isinstance(dt_iri, URIRef):
            dt_iri = OUTER.XSD.string.get_rdf_node()
        return DraftNode(DraftNode.Type.LITERAL, Literal(value, datatype=dt_iri), None, None)

    # ----- добавление триплетов -----

    def add_type(self, s: DraftNode, c: DraftNode):
        """``(subject, rdf:type, class)``."""
        self._add_triple(DraftTriple.Type.TYPE, s, OUTER.RDF.type, c)

    def add_object_property(self, s: DraftNode, p: DraftNode, o: DraftNode):
        """``(subject, object_property, individual)``."""
        self._add_triple(DraftTriple.Type.OBJECT_PROPERTY, s, p, o)

    def add_data_property(self, s: DraftNode, p: DraftNode, l: DraftNode):
        """``(subject, data_property, literal)``."""
        self._add_triple(DraftTriple.Type.DATA_PROPERTY, s, p, l)

    def add_object_property_optional(self, s: DraftNode, p: DraftNode, o: DraftNode):
        """То же, что :meth:`add_object_property`, но молча пропускает
        неполный объект (полезно для опциональных связей: должность,
        степень, звание и т. п.)."""
        if not o.is_complete():
            return
        self.add_object_property(s, p, o)

    def add_data_property_optional(self, s: DraftNode, p: DraftNode, l: DraftNode):
        """То же, что :meth:`add_data_property`, но пропускает неполный литерал."""
        if not l.is_complete():
            return
        self.add_data_property(s, p, l)

    def _add_triple(self, triple_type: DraftTriple.Type, s: DraftNode, p: DraftNode, o: DraftNode):
        self._draft_graph.add_triple(DraftTriple(triple_type, s, p, o))

    # ===== Универсальные методы для концептов ============================

    def individual(
        self,
        field_name: str,
        concept_cls: Type[BaseConcept],
        *,
        role: Optional[DraftNode] = None,
    ) -> DraftNode:
        """Создать индивид онтологии по полю и концепту.

        Применяет ``concept_cls`` к значению поля: ``parse`` → ``iri_local``
        → ``build_triples``. Добавляет в граф ``rdf:type`` базового класса
        концепта (``concept_cls.onto_class_local``) и, если задан, ``role``
        как второй тип. Возвращает :class:`DraftNode` с IRI индивида.

        Если поле пустое или концепт отвергает значение, возвращает неполный
        DraftNode с error — Connector затем пометит граф как неполный.

        Args:
            field_name: Имя поля шаблона.
            concept_cls: Подкласс :class:`BaseConcept` с
                ``kind == CLASS_INDIVIDUAL`` (Персона, Группа, Организация,
                Профиль, перечисления и т. п.).
            role: Дополнительный тип (например ``ONTO.Студент`` или
                ``ONTO.Кафедра``) — добавляется как второй ``rdf:type``.

        Raises:
            TypeError: если ``concept_cls`` не подкласс :class:`BaseConcept`
                или его ``kind != CLASS_INDIVIDUAL``.
        """
        cls = self._validate_concept_cls(concept_cls, ConceptKind.CLASS_INDIVIDUAL)

        value = self._field_values.get(field_name)
        if value is None or not str(value).strip():
            return DraftNode(DraftNode.Type.IRI, None, f"Поле '{field_name}' пустое", field_name)

        try:
            parts = cls.parse(value)
        except ConceptError as ex:
            return DraftNode(DraftNode.Type.IRI, None, str(ex), field_name)
        except Exception as ex:  # noqa: BLE001
            return DraftNode(DraftNode.Type.IRI, None, f"{cls.name}: {ex}", field_name)

        try:
            local = cls.iri_local(parts)
        except Exception as ex:  # noqa: BLE001
            return DraftNode(DraftNode.Type.IRI, None, str(ex), field_name)

        iri_node = DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[local], None, field_name)

        # rdf:type базового класса концепта.
        base_class_node = ONTO[cls.onto_class_local] if cls.onto_class_local else None
        if base_class_node is not None:
            self.add_type(iri_node, base_class_node)
        if role is not None and role.is_complete():
            self.add_type(iri_node, role)

        # Идентифицирующие литералы (:фио, :фамилия и т. п.). subject —
        # тот же iri_node; концепт переиспользует его без обёртки. Source
        # на predicate/object проставляем здесь, чтобы концепт об этом
        # не знал.
        for triple in cls.build_triples(parts, subject=iri_node):
            triple.predicate.source = field_name
            triple.object.source = field_name
            self._draft_graph.add_triple(triple)

        return iri_node

    def literal(self, field_name: str, concept_cls: Type[BaseConcept]) -> DraftNode:
        """Создать типизированный Literal по полю и концепту-``DATATYPE``.

        Применяет ``concept_cls.normalize`` к значению поля и заворачивает
        результат в ``Literal(canonical, datatype=xsd:string)``. Сейчас
        все DATATYPE-концепты порождают ``xsd:string`` (Email и Телефон —
        строки; Дата — особый случай через :meth:`field` + ``literal(XSD.date)``).

        Args:
            field_name: Имя поля шаблона.
            concept_cls: Подкласс :class:`BaseConcept` с
                ``kind == DATATYPE``.

        Raises:
            TypeError: если ``concept_cls`` не DATATYPE.
        """
        cls = self._validate_concept_cls(concept_cls, ConceptKind.DATATYPE)

        value = self._field_values.get(field_name)
        if value is None or not str(value).strip():
            return DraftNode(
                DraftNode.Type.LITERAL, None, f"Поле '{field_name}' пустое", field_name
            )

        try:
            canonical = cls.normalize(value)
        except ConceptError as ex:
            return DraftNode(DraftNode.Type.LITERAL, None, str(ex), field_name)
        except Exception as ex:  # noqa: BLE001
            return DraftNode(DraftNode.Type.LITERAL, None, f"{cls.name}: {ex}", field_name)

        # Дата → xsd:date; всё остальное (Email, Телефон) → xsd:string.
        datatype = OUTER.XSD.date.get_rdf_node() if cls is DateConcept else OUTER.XSD.string.get_rdf_node()
        return DraftNode(
            DraftNode.Type.LITERAL,
            Literal(canonical, datatype=datatype),
            None,
            field_name,
        )

    @staticmethod
    def _validate_concept_cls(
        concept_cls: Type[BaseConcept],
        expected_kind: ConceptKind,
    ) -> Type[BaseConcept]:
        if not (isinstance(concept_cls, type) and issubclass(concept_cls, BaseConcept)):
            raise TypeError(
                f"Ожидался подкласс BaseConcept, получено {concept_cls!r}"
            )
        if concept_cls.kind != expected_kind:
            method = "individual" if expected_kind == ConceptKind.CLASS_INDIVIDUAL else "literal"
            raise TypeError(
                f"{method}() требует концепт с kind={expected_kind.value}, "
                f"но {concept_cls.name} имеет kind={concept_cls.kind.value}"
            )
        return concept_cls

    # ===== Композитные хелперы (особые случаи) ===========================

    def direction(
        self,
        code_field: str,
        *,
        name_field: Optional[str] = None,
    ) -> DraftNode:
        """Направление подготовки + опциональный литерал названия.

        IRI индивида строится из кода через :class:`DirectionConcept`.
        Если задан ``name_field`` — добавляет литерал
        ``:названиеНаправления`` из этого поля (само название не входит
        в identity направления, поэтому хранится отдельно).
        """
        # Локальный импорт, чтобы не вытаскивать DirectionConcept в
        # module-level scope (он используется только здесь).
        from core.concepts.direction import DirectionConcept

        iri = self.individual(code_field, DirectionConcept)
        if name_field is not None and iri.is_complete():
            self.add_data_property_optional(
                iri, ONTO.названиеНаправления, self.field(name_field).literal()
            )
        return iri

    def thesis(
        self,
        *,
        title_field: Optional[str] = None,
        student: Optional[DraftNode] = None,
    ) -> DraftNode:
        """Индивид :ВКР.

        IRI вычисляется так:
          * если ``title_field`` задан и непустой — через
            :class:`ThesisConcept` (от темы);
          * иначе — ``hash`` от локального имени IRI студента.

        ``rdf:type :ВКР`` и (при наличии ``student``) ``:авторВКР``
        ставятся автоматически.
        """
        iri = self._build_thesis_iri(title_field=title_field, student=student)

        if iri.is_complete():
            self.add_type(iri, ONTO.ВКР)
            if student is not None and student.is_complete():
                self.add_object_property(iri, ONTO.авторВКР, student)

        return iri

    def practice(
        self,
        *,
        student: DraftNode,
        kind: DraftNode,
        year: DraftNode,
    ) -> DraftNode:
        """Индивид :Практика для тройки (студент, вид, год).

        IRI считается через :class:`PracticeConcept.from_components` из
        локальных имён студента и вида + строкового значения ``year``.
        Добавляет ``rdf:type :Практика`` и identifying-связи
        ``:практикантВПрактике``, ``:видПрактики``, ``:учебныйГодПрактики``.

        Args:
            student: Уже построенный индивид :Персона (через
                ``b.individual(..., PersonConcept, role=ONTO.Студент)``).
            kind: Уже построенный индивид :ВидПрактики.
            year: Литерал-DraftNode со значением учебного года. Шаблон
                сам решает, откуда взять год: отдельное поле
                (``b.field("academic_year").literal()``), производное
                значение (``b.field("start_date").part(DateConcept,
                "year").literal()``), константа
                (``b.const_literal("2024/2025")``) и т. п. Значение года
                читается через ``str(year.get_rdf_node())`` и идёт в
                идентифицирующую тройку IRI Практики.
        """
        if not student.is_complete():
            return DraftNode(DraftNode.Type.IRI, None, "Практика: студент неполный", None)
        if not kind.is_complete():
            return DraftNode(DraftNode.Type.IRI, None, "Практика: вид практики неполный", None)
        if not year.is_complete():
            return DraftNode(
                DraftNode.Type.IRI, None,
                "Практика: значение года неполное",
                year.source,
            )

        year_value = str(year.get_rdf_node())
        if not year_value.strip():
            return DraftNode(
                DraftNode.Type.IRI, None, "Практика: значение года пустое", year.source
            )

        student_local = self._extract_local_name(student)
        kind_local = self._extract_local_name(kind)
        if student_local is None or kind_local is None:
            return DraftNode(
                DraftNode.Type.IRI, None,
                "Практика: IRI студента или вида не в пространстве предметной области",
                year.source,
            )

        try:
            parts = PracticeConcept.from_components(student_local, kind_local, year_value)
            local = PracticeConcept.iri_local(parts)
        except ConceptError as ex:
            return DraftNode(DraftNode.Type.IRI, None, str(ex), year.source)

        iri = DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[local], None, year.source)

        self.add_type(iri, ONTO.Практика)
        self.add_object_property(iri, ONTO.практикантВПрактике, student)
        self.add_object_property(iri, ONTO.видПрактики, kind)
        self.add_data_property(iri, ONTO.учебныйГодПрактики, year)
        return iri

    # ----- внутренние хелперы для композитов -----

    def _build_thesis_iri(
        self,
        *,
        title_field: Optional[str],
        student: Optional[DraftNode],
    ) -> DraftNode:
        # Сначала пробуем построить от темы.
        if title_field is not None:
            value = self._field_values.get(title_field)
            if value and str(value).strip():
                try:
                    parts = ThesisConcept.parse(value)
                    return DraftNode(
                        DraftNode.Type.IRI,
                        _RDFLIB_ONTO[ThesisConcept.iri_local(parts)],
                        None,
                        title_field,
                    )
                except ConceptError as ex:
                    return DraftNode(DraftNode.Type.IRI, None, str(ex), title_field)

        # Fallback — от IRI студента.
        if student is None or not student.is_complete():
            return DraftNode(
                DraftNode.Type.IRI, None,
                "Не указан title_field и нет студента — IRI ВКР построить невозможно",
                None,
            )

        student_local = self._extract_local_name(student)
        if student_local is None:
            return DraftNode(
                DraftNode.Type.IRI, None,
                "IRI студента не в пространстве предметной области",
                None,
            )
        return DraftNode(
            DraftNode.Type.IRI,
            _RDFLIB_ONTO["ВКР_" + short_sha1(student_local)],
            None,
            None,
        )

    @staticmethod
    def _extract_local_name(node: DraftNode) -> Optional[str]:
        """Локальное имя IRI узла (без префикса проекта). None — если
        IRI не из пространства предметной области."""
        rdf_node = node.get_rdf_node()
        if rdf_node is None:
            return None
        s = str(rdf_node)
        if not s.startswith(SUBJECT_NAMESPACE_IRI):
            return None
        local = s[len(SUBJECT_NAMESPACE_IRI):]
        return local or None
