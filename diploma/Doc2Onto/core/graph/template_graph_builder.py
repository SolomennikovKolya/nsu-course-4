from rdflib import Namespace
from rdflib import URIRef, Literal
from typing import Optional, Dict, Any, Iterable

from app.settings import SUBJECT_NAMESPACE_IRI
from core.graph.draft_graph import DraftNode, DraftTriple, DraftGraph
from core.graph.value_transformer import ValueTransformFunc, ValueTransformer
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
        return DraftNode(DraftNode.Type.IRI, uri, None, None)

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


_XSD_DATE = OUTER.XSD.date.get_rdf_node()
_XSD_DATETIME = OUTER.XSD.dateTime.get_rdf_node()


def _autonormalize_for_datatype(value: str, datatype_iri: URIRef):
    """
    Если ``datatype_iri`` это xsd:date или xsd:dateTime, приводит ``value``
    к ISO-формату через :class:`ValueTransformer.date`. Возвращает либо
    нормализованную строку, либо исходную (если для типа нормализация не
    нужна), либо :class:`Exception` (если нормализация требовалась, но не
    удалась — её нужно показать пользователю как ошибку поля).

    Для уже-ISO значений (например, ``2025-05-19``) обработка идемпотентна.
    """
    if datatype_iri == _XSD_DATE or datatype_iri == _XSD_DATETIME:
        try:
            data = ValueTransformer.date(value)
        except Exception as ex:
            return ex
        iso = data.get("iso")
        return iso if iso else value
    return value


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
            return DraftNode(DraftNode.Type.IRI, value, error, self._source_field_name)

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

        Для xsd:date / xsd:dateTime значение автоматически нормализуется
        к ISO-формату через :class:`ValueTransformer.date` (если значение
        ещё не в ISO). Это позволяет в шаблоне писать
        ``b.field("start_date").literal(OUTER.XSD.date)`` без явного
        ``.transform(ValueTransformer.date, key="iso")`` — иначе rdflib
        отказывается приводить «19.05.2025» к xsd:date и портит граф.
        """
        def node(value: Optional[Literal], error: Optional[str]) -> DraftNode:
            return DraftNode(DraftNode.Type.LITERAL, value, error, self._source_field_name)

        if self._error is not None:
            return node(None, self._error)

        value = self._get_value()
        if value is None:
            error = "Значение поля отсутствует; Невозможно построить Literal из None"
            return node(None, error)

        dt_iri = datatype.get_rdf_node() if datatype is not None else OUTER.XSD.string.get_rdf_node()
        if not isinstance(dt_iri, URIRef):
            error = "Неверный тип datatype: ожидается именованная сущность (имеющая IRI)"
            return node(None, error)

        if not self._transform_called():
            normalized = _autonormalize_for_datatype(value, dt_iri)
            if isinstance(normalized, Exception):
                return node(None, str(normalized))
            value = normalized

        return node(Literal(value, datatype=dt_iri), None)


class NoneValueProxy(ValueProxy):
    """Заглушка на случай, если поле не существует в шаблоне."""

    def __init__(self, field_name: str):
        super().__init__(field_name, None)
        self.ERROR = f"Поле {field_name} не существует в шаблоне"

    def transform(self, fn: ValueTransformFunc, key: str) -> "NoneValueProxy":
        return self

    def iri(self) -> DraftNode:
        return DraftNode(DraftNode.Type.IRI, None, self.ERROR, None)

    def literal(self, datatype: Optional[DraftNode] = None) -> DraftNode:
        return DraftNode(DraftNode.Type.LITERAL, None, self.ERROR, None)


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
        dt_iri = datatype.get_rdf_node() if datatype is not None else None
        if not isinstance(dt_iri, URIRef):
            dt_iri = OUTER.XSD.string.get_rdf_node()

        return DraftNode(DraftNode.Type.LITERAL, Literal(value, datatype=dt_iri), None, None)

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

    def add_object_property_optional(self, s: DraftNode, p: DraftNode, o: DraftNode):
        """
        То же, что :meth:`add_object_property`, но молча пропускает триплет, если
        объект неполный (например, перечисление не найдено или поле пустое).
        Используется для опциональных связей: должность, степень, звание и т. п.
        """
        if not o.is_complete():
            return
        self.add_object_property(s, p, o)

    def add_data_property_optional(self, s: DraftNode, p: DraftNode, l: DraftNode):
        """То же, что :meth:`add_data_property`, но пропускает триплет с неполным литералом."""
        if not l.is_complete():
            return
        self.add_data_property(s, p, l)

    def _add_triple(self, triple_type: DraftTriple.Type, s: DraftNode, p: DraftNode, o: DraftNode):
        self._draft_graph.add_triple(DraftTriple(triple_type, s, p, o))

    # ----- высокоуровневые хелперы предметной области -----

    # Эти методы скрывают за собой типовой набор триплетов «индивид + базовые
    # литералы» для часто встречающихся классов онтологии. Они работают по
    # принципу: «получи имя поля → построй IRI индивида → добавь тип →
    # добавь стандартные литералы (фио/название/код)». В случае отсутствия
    # поля или ошибки трансформации возвращается неполный DraftNode и
    # триплеты не добавляются — Connector затем пометит граф как неполный.

    def person(
        self,
        name_field: str,
        *,
        role: Optional[DraftNode] = None,
    ) -> DraftNode:
        """
        Регистрирует индивида :Персона по полю с ФИО и возвращает его IRI.

        Делает за один вызов:
          * IRI = ONTO.person_<sha1[:12]> от канонической формы (морфологически
            нормализованной к именительному падежу),
          * rdf:type :Персона и, если задано, ``role`` (например, :Студент или :Сотрудник),
          * литералы :фио, :фамилия, :имя, :отчество (отчество — только если есть).

        Если поле отсутствует или ФИО не парсится, возвращает неполный IRI с error.
        """
        return self._domain_individual(
            field=name_field,
            transformer=ValueTransformer.person,
            base_class=ONTO.Персона,
            extra_class=role,
            literals=[
                (ONTO.фио, "name"),
                (ONTO.фамилия, "last_name"),
                (ONTO.имя, "first_name"),
                (ONTO.отчество, "middle_name"),
            ],
            iri_key="hash",
        )

    def organization(
        self,
        name_field: str,
        *,
        role: Optional[DraftNode] = None,
    ) -> DraftNode:
        """
        Регистрирует индивида :Организация по полю с полным наименованием.

        Делает за один вызов:
          * IRI = ONTO.org_<sha1[:12]> от нормализованного названия,
          * rdf:type :Организация и, если задано, ``role`` (:ВнешняяОрганизация / :Университет / :Кафедра / …),
          * литерал :названиеОрганизации.
        """
        return self._domain_individual(
            field=name_field,
            transformer=ValueTransformer.organization,
            base_class=ONTO.Организация,
            extra_class=role,
            literals=[(ONTO.названиеОрганизации, "name")],
            iri_key="hash",
        )

    def profile(self, name_field: str) -> DraftNode:
        """
        Регистрирует индивида :Профиль по полю с названием профиля подготовки.

        Добавляет тип :Профиль и литерал :названиеПрофиля.
        """
        return self._domain_individual(
            field=name_field,
            transformer=ValueTransformer.profile,
            base_class=ONTO.Профиль,
            extra_class=None,
            literals=[(ONTO.названиеПрофиля, "name")],
            iri_key="hash",
        )

    def group(self, number_field: str) -> DraftNode:
        """
        Регистрирует индивида :Группа по полю с номером группы.

        IRI — стабильный local-name :Группа_<номер>. Добавляет тип :Группа и
        литерал :номерГруппы.
        """
        return self._domain_individual(
            field=number_field,
            transformer=ValueTransformer.group,
            base_class=ONTO.Группа,
            extra_class=None,
            literals=[(ONTO.номерГруппы, "number")],
            iri_key="local",
        )

    def direction(
        self,
        code_field: str,
        *,
        name_field: Optional[str] = None,
    ) -> DraftNode:
        """
        Регистрирует индивида :НаправлениеПодготовки по полю с кодом (XX.XX.XX).

        IRI — :Направление_XX_XX_XX. Добавляет тип, литерал :кодНаправления и,
        если задано, литерал :названиеНаправления из ``name_field``.
        """
        iri = self._domain_individual(
            field=code_field,
            transformer=ValueTransformer.direction,
            base_class=ONTO.НаправлениеПодготовки,
            extra_class=None,
            literals=[(ONTO.кодНаправления, "code")],
            iri_key="local",
        )

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
        """
        Регистрирует индивида :ВКР.

        IRI вычисляется так:
          * если задан ``title_field`` и поле непустое — хеш от нормализованной темы
            (``thesis_<sha1[:12]>``) + добавляется литерал :темаВКР;
          * иначе IRI считается от IRI студента (``thesis_<sha1[:12]>``).

        Тип :ВКР и (при наличии student) объектное свойство :авторВКР добавляются
        автоматически.
        """
        iri = self._build_thesis_iri(title_field=title_field, student=student)

        if iri.is_complete():
            self.add_type(iri, ONTO.ВКР)
            if student is not None and student.is_complete():
                self.add_object_property(iri, ONTO.авторВКР, student)

            if title_field is not None:
                self.add_data_property_optional(
                    iri, ONTO.темаВКР, self.field(title_field).literal()
                )

        return iri

    def practice(
        self,
        *,
        student: DraftNode,
        kind: DraftNode,
        year_field: str,
    ) -> DraftNode:
        """
        Регистрирует индивида :Практика для (студент, вид практики, учебный год).

        IRI = ONTO.practice_<sha1[:12]> от тройки. Добавляет тип :Практика,
        литерал :учебныйГодПрактики, объектные :практикантВПрактике и :видПрактики.
        """
        if not student.is_complete():
            return DraftNode(DraftNode.Type.IRI, None, "Практика: студент неполный", None)
        if not kind.is_complete():
            return DraftNode(DraftNode.Type.IRI, None, "Практика: вид практики неполный", None)

        year_value = self._field_values.get(year_field)
        if not year_value:
            return DraftNode(DraftNode.Type.IRI, None, f"Практика: поле '{year_field}' пустое", year_field)

        try:
            data = ValueTransformer.practice({
                "person": str(student.get_rdf_node()),
                "kind": str(kind.get_rdf_node()),
                "year": year_value,
            })
        except Exception as ex:
            return DraftNode(DraftNode.Type.IRI, None, str(ex), year_field)

        iri = DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[data["hash"]], None, year_field)

        self.add_type(iri, ONTO.Практика)
        self.add_object_property(iri, ONTO.практикантВПрактике, student)
        self.add_object_property(iri, ONTO.видПрактики, kind)
        self.add_data_property(
            iri, ONTO.учебныйГодПрактики,
            self.field(year_field).literal(),
        )
        return iri

    # ----- индивиды перечислений (без побочных эффектов) -----

    def position(self, field_name: str) -> DraftNode:
        """Возвращает IRI индивида перечисления :Должность по строковому значению поля."""
        return self._enum_individual(field_name, ValueTransformer.position)

    def degree(self, field_name: str) -> DraftNode:
        """Возвращает IRI индивида перечисления :УченаяСтепень."""
        return self._enum_individual(field_name, ValueTransformer.degree)

    def title(self, field_name: str) -> DraftNode:
        """Возвращает IRI индивида перечисления :УченоеЗвание."""
        return self._enum_individual(field_name, ValueTransformer.title)

    def practice_kind(self, field_name: str) -> DraftNode:
        """Возвращает IRI индивида перечисления :ВидПрактики."""
        return self._enum_individual(field_name, ValueTransformer.practice_kind)

    def grade(self, field_name: str) -> DraftNode:
        """Возвращает IRI индивида перечисления :Оценка."""
        return self._enum_individual(field_name, ValueTransformer.grade)

    # ----- утилитарные хелперы для типизированных литералов ---------------

    def date(self, field_name: str) -> DraftNode:
        """
        Возвращает Literal с типом xsd:date по строковому значению поля.

        Значение нормализуется через :class:`ValueTransformer.date`, поэтому
        принимаются и ISO (``2025-05-19``), и русские форматы
        (``19.05.2025``, ``«29» сентября 2025 г.``). При ошибке парсинга
        возвращается неполный DraftNode с описанием ошибки — триплет с ним
        не попадёт в граф (используй вместе с :meth:`add_data_property_optional`,
        если поле опциональное).
        """
        return self.field(field_name).literal(OUTER.XSD.date)

    # ----- внутренние общие реализации высокоуровневых хелперов -----

    def _domain_individual(
        self,
        *,
        field: str,
        transformer: ValueTransformFunc,
        base_class: DraftNode,
        extra_class: Optional[DraftNode],
        literals: Iterable,
        iri_key: str,
    ) -> DraftNode:
        value = self._field_values.get(field)
        if value is None or not str(value).strip():
            return DraftNode(DraftNode.Type.IRI, None, f"Поле '{field}' пустое", field)

        try:
            data = transformer(value)
        except Exception as ex:
            return DraftNode(DraftNode.Type.IRI, None, str(ex), field)

        local = data.get(iri_key)
        if not local:
            return DraftNode(
                DraftNode.Type.IRI, None,
                f"Трансформер не вернул значение по ключу '{iri_key}'", field,
            )

        iri = DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[local], None, field)
        self.add_type(iri, base_class)
        if extra_class is not None and extra_class.is_complete():
            self.add_type(iri, extra_class)

        for predicate, key in literals:
            literal_value = data.get(key)
            if literal_value is None or str(literal_value).strip() == "":
                continue
            self._add_string_literal(iri, predicate, str(literal_value), source=field)

        return iri

    def _enum_individual(
        self,
        field_name: str,
        transformer: ValueTransformFunc,
    ) -> DraftNode:
        value = self._field_values.get(field_name)
        if value is None or not str(value).strip():
            return DraftNode(DraftNode.Type.IRI, None, f"Поле '{field_name}' пустое", field_name)

        try:
            data = transformer(value)
        except Exception as ex:
            return DraftNode(DraftNode.Type.IRI, None, str(ex), field_name)

        local = data.get("local")
        if not local:
            return DraftNode(DraftNode.Type.IRI, None, "Перечисление не вернуло local", field_name)
        return DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[local], None, field_name)

    def _build_thesis_iri(
        self,
        *,
        title_field: Optional[str],
        student: Optional[DraftNode],
    ) -> DraftNode:
        if title_field is not None:
            value = self._field_values.get(title_field)
            if value and str(value).strip():
                try:
                    data = ValueTransformer.thesis(value)
                    return DraftNode(
                        DraftNode.Type.IRI, _RDFLIB_ONTO[data["hash"]], None, title_field
                    )
                except Exception as ex:
                    return DraftNode(DraftNode.Type.IRI, None, str(ex), title_field)

        if student is None or not student.is_complete():
            return DraftNode(
                DraftNode.Type.IRI, None,
                "Не указан title_field и нет студента — IRI ВКР построить невозможно",
                None,
            )

        student_iri = str(student.get_rdf_node())
        if not student_iri.startswith(SUBJECT_NAMESPACE_IRI):
            return DraftNode(
                DraftNode.Type.IRI, None,
                f"IRI студента не в пространстве предметной области: {student_iri}",
                None,
            )
        student_local = student_iri[len(SUBJECT_NAMESPACE_IRI):]
        h = "ВКР_" + ValueTransformer._hash(student_local)
        return DraftNode(DraftNode.Type.IRI, _RDFLIB_ONTO[h], None, None)

    def _add_string_literal(
        self,
        s: DraftNode,
        p: DraftNode,
        value: Optional[str],
        *,
        source: Optional[str],
    ):
        if value is None or str(value).strip() == "":
            return

        node = DraftNode(
            DraftNode.Type.LITERAL,
            Literal(value, datatype=OUTER.XSD.string.get_rdf_node()),
            None,
            source,
        )
        self.add_data_property(s, p, node)
