# ПРИЛОЖЕНИЯ

## Приложение А

### XSD-схема унифицированной модели представления документов (UDDM)

Ниже приведён полный текст XSD-схемы, формализующей структуру
унифицированного представления документов в разработанной системе
(см. главу 2, раздел 2.2).

```xml
<?xml version="1.0" encoding="UTF-8"?>

<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

    <!-- Корневой элемент документа -->
    <xs:element name="root">
        <xs:complexType>
            <xs:sequence>
                <xs:group ref="blockGroup" minOccurs="0" maxOccurs="unbounded"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>

    <!-- Блок: текст, список или таблица -->
    <xs:group name="blockGroup">
        <xs:choice>
            <xs:element name="text"  type="TextType"/>
            <xs:element name="list"  type="ListType"/>
            <xs:element name="table" type="TableType"/>
        </xs:choice>
    </xs:group>

    <!-- Текстовый блок: последовательность абзацев -->
    <xs:complexType name="TextType">
        <xs:sequence>
            <xs:element name="p" type="xs:string"
                        minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

    <!-- Список: последовательность элементов -->
    <xs:complexType name="ListType">
        <xs:sequence>
            <xs:element name="item" type="ItemType"
                        minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

    <!-- Элемент списка: один или несколько вложенных блоков -->
    <xs:complexType name="ItemType">
        <xs:sequence>
            <xs:group ref="blockGroup"
                      minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

    <!-- Таблица: последовательность строк -->
    <xs:complexType name="TableType">
        <xs:sequence>
            <xs:element name="row" type="RowType"
                        minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

    <!-- Строка таблицы: последовательность ячеек -->
    <xs:complexType name="RowType">
        <xs:sequence>
            <xs:element name="cell" type="CellType"
                        minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

    <!-- Ячейка таблицы: один или несколько вложенных блоков -->
    <xs:complexType name="CellType">
        <xs:sequence>
            <xs:group ref="blockGroup"
                      minOccurs="1" maxOccurs="unbounded"/>
        </xs:sequence>
    </xs:complexType>

</xs:schema>
```

---

## Приложение Б

### Пример документа в формате UDDM

Ниже приведён сокращённый пример унифицированного представления
документа — заявления обучающегося на прохождение практики (тип
документа описан шаблоном в Приложении Г). Пример иллюстрирует
использование всех трёх типов блоков (текст, список, таблица),
вложенных абзацев и табличных данных.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>

    <text>
        <p>Министерство науки и высшего образования Российской Федерации</p>
        <p>Новосибирский национальный исследовательский государственный университет</p>
        <p>Факультет информационных технологий</p>
        <p>Кафедра общей информатики</p>
    </text>

    <text>
        <p>ЗАЯВЛЕНИЕ</p>
        <p>о направлении на практику</p>
    </text>

    <text>
        <p>От обучающегося Соломенникова Николая Александровича (Ф.И.О.)</p>
        <p>4 курса, группы № 22204</p>
        <p>направление 09.03.01 (код и наименование направления)</p>
        <p>Информатика и вычислительная техника</p>
        <p>направленность (профиль) Программная инженерия и компьютерные науки (наименование профиля)</p>
    </text>

    <text>
        <p>Прошу направить меня на производственную практику</p>
        <p>(указывается наименование практики)</p>
        <p>в ФГБУН Институт математики им. С. Л. Соболева СО РАН</p>
        <p>630090, г. Новосибирск, пр. Академика Коптюга, 4</p>
    </text>

    <table>
        <row>
            <cell><text><p>Дата начала практики</p></text></cell>
            <cell><text><p>29.09.2025</p></text></cell>
        </row>
        <row>
            <cell><text><p>Дата окончания практики</p></text></cell>
            <cell><text><p>23.12.2025</p></text></cell>
        </row>
    </table>

    <text>
        <p>Дата: «20» сентября 2025 г.</p>
    </text>

    <text>
        <p>Руководитель ВКР Пальчунов Дмитрий Евгеньевич, зав. кафедрой</p>
        <p>(Ф.И.О. полностью) (должность)</p>
    </text>

</root>
```

---

## Приложение В

### Фрагмент схемы онтологии кафедры

Ниже приведён сокращённый фрагмент схемы онтологии кафедры,
иллюстрирующий ключевые архитектурные решения: трёхзначное
перечисление политик слияния, аннотация `:mergePolicy`,
организация классов и их свойств. Полный текст схемы доступен в
исходных материалах системы.

```turtle
@prefix :     <http://doc2onto.org/ontology#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://doc2onto.org/ontology> rdf:type owl:Ontology ;
    rdfs:label "Онтология учебного процесса кафедры"@ru .


# ===== Политики слияния фактов (см. главу 2, раздел 2.8.1) =====

:MergePolicy rdf:type owl:Class ;
    rdfs:label "Политика слияния фактов"@ru .

:Policy_Set        rdf:type owl:NamedIndividual, :MergePolicy ;
    rdfs:label "set"@ru ;
    rdfs:comment "Полная замена (s, p, *) → (s, p, o_new)." .

:Policy_SetByDate  rdf:type owl:NamedIndividual, :MergePolicy ;
    rdfs:label "set-by-date"@ru ;
    rdfs:comment "Замена только если effective_date нового факта ≥ существующего." .

:Policy_Add        rdf:type owl:NamedIndividual, :MergePolicy ;
    rdfs:label "add"@ru ;
    rdfs:comment "Multi-valued: чистый add (дефолт)." .

:mergePolicy rdf:type owl:AnnotationProperty ;
    rdfs:label "политика слияния"@ru ;
    rdfs:domain rdf:Property ;
    rdfs:range  :MergePolicy .


# ===== Классы (фрагмент) =====

:Агент rdf:type owl:Class ;
    rdfs:label "Агент"@ru .

:Персона rdf:type owl:Class ;
    rdfs:subClassOf :Агент ;
    rdfs:label "Персона"@ru ;
    rdfs:comment """IRI индивида формируется как детерминированный хеш от
        нормализованного представления ФИО.""" .

:Студент rdf:type owl:Class ;
    rdfs:subClassOf :Персона ;
    rdfs:label "Студент"@ru .

:Сотрудник rdf:type owl:Class ;
    rdfs:subClassOf :Персона ;
    rdfs:label "Сотрудник"@ru .

:Группа rdf:type owl:Class ;
    rdfs:label "Учебная группа"@ru .

:ВКР rdf:type owl:Class ;
    rdfs:label "Выпускная квалификационная работа"@ru ;
    rdfs:comment "IRI — хеш от IRI студента (одна ВКР на студента)." .

:Практика rdf:type owl:Class ;
    rdfs:label "Практика"@ru ;
    rdfs:comment "IRI — хеш от пары (IRI студента, дата начала)." .

# Дизъюнктность: персона и организация не пересекаются.
[] rdf:type owl:AllDisjointClasses ;
   owl:members ( :Персона :Организация ) .


# ===== Свойства (фрагмент) =====

# Идентифицирующее свойство — полная замена.
:фамилия rdf:type owl:DatatypeProperty ;
    rdfs:domain :Персона ;
    rdfs:range  xsd:string ;
    :mergePolicy :Policy_Set .

# Изменяющееся во времени состояние — замена по дате.
:обучаетсяВГруппе rdf:type owl:ObjectProperty ;
    rdfs:domain :Студент ;
    rdfs:range  :Группа ;
    :mergePolicy :Policy_SetByDate .

:темаВКР rdf:type owl:DatatypeProperty ;
    rdfs:domain :ВКР ;
    rdfs:range  xsd:string ;
    :mergePolicy :Policy_SetByDate .

# Множественное свойство — добавление.
:телефон rdf:type owl:DatatypeProperty ;
    rdfs:domain :Персона ;
    rdfs:range  xsd:string ;
    :mergePolicy :Policy_Add .

# Идентифицирующая связь — полная замена.
:авторВКР rdf:type owl:ObjectProperty ;
    rdfs:domain :ВКР ;
    rdfs:range  :Студент ;
    :mergePolicy :Policy_Set .
```

---

## Приложение Г

### Пример кода шаблона извлечения знаний

Ниже приведён пример кода шаблона для класса документа «заявление
обучающегося на прохождение практики». Шаблон включает все три
обязательных метода контракта (см. главу 2, раздел 2.4.1):
правила распознавания принадлежности документа классу
(`classify`), описание извлекаемых полей (`fields`) и правила
сборки графа фактов (`build`).

```python
from typing import List

from core import *


class TemplateCode(BaseTemplateCode):

    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        # Распознаётся либо по имени файла, либо по якорным фразам.
        name = (doc_name or "").lower()
        if all(w in name for w in ["заявление", "практику", "пиикн"]):
            return True

        full_text = str(uddm.root).lower()
        return all(w in full_text for w in [
            "заявление", "прошу направить меня", "практику",
        ])

    def fields(self) -> List[Field]:
        return [
            Field(
                "student_name", "ФИО обучающегося",
                sel().find(ElementType.P, Predicate.contains_text("(Ф.И.О.)")),
                ext().before("(Ф.И.О.)").keep_letters_and_spaces().normalize_spaces(),
                norm().concept(PersonConcept),
            ),
            Field(
                "course_number", "Номер курса обучения",
                sel().find(ElementType.P, Predicate.contains_text("курса")),
                ext().regex(r"(\d+)\s*курса", group=1),
                norm().integer().in_range(1, 4),
            ),
            Field(
                "group_number", "Номер учебной группы",
                sel().find(ElementType.P, Predicate.contains_text("группы №")),
                ext().regex(r"группы\s*№\s*([0-9]+)", group=1),
                norm().concept(GroupConcept),
            ),
            Field(
                "direction_code", "Код направления подготовки",
                sel().find(ElementType.P, Predicate.contains_text("направление")),
                ext().regex(r"(\d{2}\.\d{2}\.\d{2})", group=1),
                norm().concept(DirectionConcept),
            ),
            Field(
                "direction_name", "Наименование направления подготовки",
                sel().find(ElementType.P, Predicate.contains_text(
                    "(код и наименование направления)")).previous_element(),
                ext().regex(r"\d{2}\.\d{2}\.\d{2}\s*(.+)$", group=1),
                norm(),
            ),
            Field(
                "profile_name", "Наименование профиля подготовки",
                sel().find(ElementType.P, Predicate.contains_text(
                    "направленность (профиль)")),
                ext().after("направленность (профиль)"),
                norm(),
            ),
            Field(
                "organization_full_name", "Полное наименование организации",
                sel().find(ElementType.P, Predicate.contains_text(
                    "(указывается наименование практики)")).previous_element(),
                ext(),
                norm(),
            ),
            Field(
                "application_date", "Дата заявления",
                sel().find(ElementType.P, Predicate.contains_text("Дата:")),
                ext().after("Дата:"),
                norm().concept(DateConcept),
            ),
            Field(
                "supervisor_name", "ФИО руководителя ВКР",
                sel().find(ElementType.P, Predicate.contains_text("Руководитель ВКР")),
                ext().regex(
                    r"Руководитель ВКР.*?"
                    r"([А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+)",
                    group=1,
                ),
                norm().concept(PersonConcept),
            ),
            Field(
                "supervisor_position", "Должность руководителя ВКР",
                sel().find(ElementType.P, Predicate.contains_text("Руководитель ВКР")),
                ext().regex(
                    r"(зав\.\s*кафедрой|доцент|профессор|"
                    r"старший\s+преподаватель|преподаватель)",
                    group=1,
                ),
                norm().concept(PositionConcept),
            ),
        ]

    def build(self, b: TemplateGraphBuilder):
        # Студент — центральный индивид документа.
        student = b.individual("student_name", PersonConcept,
                               role=ONTO.Студент)

        # Учебная траектория студента.
        b.add_object_property(student, ONTO.обучаетсяВГруппе,
            b.individual("group_number", GroupConcept))
        b.add_object_property(student, ONTO.обучаетсяНаНаправлении,
            b.direction("direction_code", name_field="direction_name"))
        b.add_object_property(student, ONTO.имеетПрофиль,
            b.individual("profile_name", ProfileConcept))

        # Профильная организация места практики.
        b.individual("organization_full_name", OrganizationConcept,
                     role=ONTO.ВнешняяОрганизация)

        # Руководитель ВКР с опциональной должностью.
        supervisor = b.individual("supervisor_name", PersonConcept,
                                  role=ONTO.Сотрудник)
        b.add_object_property_optional(supervisor, ONTO.занимаетДолжность,
            b.individual("supervisor_position", PositionConcept))

        # ВКР — композитный индивид (см. главу 2, раздел 2.6.4).
        thesis = b.thesis(student=student)
        b.add_object_property(thesis, ONTO.руководительВКР, supervisor)
        b.add_object_property(student, ONTO.имеетВКР, thesis)
```
