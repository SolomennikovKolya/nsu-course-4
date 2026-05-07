"""
Компактное текстовое представление схемы онтологии для промптов LLM-агентов.

Парсит ``resources/onto/schema.ttl`` и формирует Markdown-сводку:
  - дерево классов (label, comment, рекомендация по форме IRI),
  - именованные индивиды закрытых перечислений,
  - таблицы объектных и дата-свойств с domain → range и :mergePolicy,
  - короткое примечание о практиках построения IRI и сохранении литералов.

Сводка кешируется по mtime файла схемы.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef

from app.settings import ONTOLOGY_SCHEMA_PATH, SUBJECT_NAMESPACE_IRI


_ONTO = Namespace(SUBJECT_NAMESPACE_IRI)
_MERGE_POLICY = _ONTO["mergePolicy"]


# Рекомендации по форме IRI и нужным хелперам предметно-ориентированного DSL.
# Все «обычные» индивиды строятся через b.individual(field, ConceptCls, role=...);
# концепт сам решает, как нормализовать значение, посчитать IRI и какие
# идентифицирующие литералы добавить. Композитные/особые случаи
# (Направление с названием, ВКР от студента, Практика из тройки) —
# отдельные методы билдера. Эта информация зашита здесь, потому что в
# TBox её нет.
_IRI_GUIDE: Dict[str, Optional[str]] = {
    "Персона": 'b.individual("<поле_фио>", PersonConcept, role=ONTO.Персона) — IRI = :Персона_<sha1>, литералы :фио/:фамилия/:имя/:отчество и тип добавляются автоматически',
    "Студент": 'b.individual("<поле_фио>", PersonConcept, role=ONTO.Студент) — то же, плюс тип :Студент',
    "Сотрудник": 'b.individual("<поле_фио>", PersonConcept, role=ONTO.Сотрудник) — то же, плюс тип :Сотрудник',
    "Организация": 'b.individual("<поле_названия>", OrganizationConcept) — IRI = :Организация_<sha1>, литерал :названиеОрганизации',
    "Университет": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.Университет)',
    "Факультет": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.Факультет)',
    "Кафедра": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.Кафедра)',
    "Лаборатория": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.Лаборатория)',
    "ВнешняяОрганизация": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.ВнешняяОрганизация)',
    "СтруктурноеПодразделение": 'b.individual("<поле_названия>", OrganizationConcept, role=ONTO.СтруктурноеПодразделение)',
    "Группа": 'b.individual("<поле_номера>", GroupConcept) — IRI = :Группа_<номер>, литерал :номерГруппы',
    "НаправлениеПодготовки": 'b.direction("<поле_кода>", name_field="<поле_названия>") — IRI = :Направление_<код>, литералы :кодНаправления и :названиеНаправления',
    "Профиль": 'b.individual("<поле_названия>", ProfileConcept) — IRI = :Профиль_<sha1>, литерал :названиеПрофиля',
    "ВКР": 'b.thesis(title_field="<поле_темы>", student=<student_iri>) — IRI = :ВКР_<sha1>, тип :ВКР, связь :авторВКР',
    "Практика": 'b.practice(student=<student_iri>, kind=<kind_iri>, year_field="<поле_года>") — IRI = :Практика_<sha1>',
    "Должность": 'b.individual("<поле_должности>", PositionConcept) — выбирает индивид перечисления :Должность_X',
    "УченаяСтепень": 'b.individual("<поле_степени>", DegreeConcept) — выбирает индивид перечисления :УченаяСтепень_X',
    "УченоеЗвание": 'b.individual("<поле_звания>", TitleConcept) — выбирает индивид перечисления :УченоеЗвание_X',
    "ВидПрактики": 'b.individual("<поле_вида_практики>", PracticeKindConcept) — выбирает индивид перечисления :ВидПрактики_X',
    "ОценкаПрактики": 'b.individual("<поле_оценки>", GradeConcept) — выбирает индивид перечисления :Оценка_X',
    "Агент": None,
    "АкадемическаяАктивность": None,
    "MergePolicy": None,
}

_POLICY_LABELS = {
    "Policy_Set": "set",
    "Policy_SetByDate": "set-by-date",
    "Policy_Add": "add",
}


@dataclass(frozen=True)
class _ClassInfo:
    local: str
    label: str
    comment: str
    parent: Optional[str]


@dataclass(frozen=True)
class _PropertyInfo:
    local: str
    label: str
    domain: str
    range: str
    policy: str
    comment: str


@dataclass(frozen=True)
class _IndividualInfo:
    local: str
    label: str


_cache: Dict[str, Tuple[float, str]] = {}


def build_schema_summary(schema_path: Optional[Path] = None) -> str:
    """Возвращает Markdown-сводку схемы; кеш — по mtime файла."""
    path = Path(schema_path) if schema_path else ONTOLOGY_SCHEMA_PATH
    if not path.exists():
        return f"(онтология не найдена по пути {path})"

    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]

    summary = _build(path)
    _cache[key] = (mtime, summary)
    return summary


def _build(path: Path) -> str:
    g = Graph()
    g.parse(path, format="turtle")

    classes = _collect_classes(g)
    obj_props, data_props = _collect_properties(g)
    enum_individuals = _collect_enum_individuals(g, classes)

    lines: List[str] = []
    lines.append("Базовый namespace: " + SUBJECT_NAMESPACE_IRI)
    lines.append('Доступ из шаблона: ONTO.<local_name>, например ONTO.Студент или ONTO.фамилия.')
    lines.append("")

    lines.append("### Иерархия классов")
    lines.append("Под каждым классом — короткий label и (если есть) рекомендация по форме IRI.")
    lines.append("")
    lines.extend(_render_class_tree(classes))
    lines.append("")

    lines.append("### Именованные индивиды перечислений")
    lines.append(
        "Закрытые списки. Бери индивид по точному local-name через ONTO.<local>. "
        "Если в тексте встречается label — отображай его на нужный local-name через свою таблицу."
    )
    lines.append("")
    lines.extend(_render_enum_individuals(enum_individuals))
    lines.append("")

    lines.append("### Объектные свойства (rdfs:domain → rdfs:range)")
    lines.append("Колонка policy задаёт правило слияния фактов при пополнении модели.")
    lines.append("")
    lines.extend(_render_property_table(obj_props))
    lines.append("")

    lines.append("### Дата-свойства")
    lines.append("")
    lines.extend(_render_property_table(data_props))
    lines.append("")

    lines.append("### Политики слияния")
    lines.append(
        "- set — единственное стабильное значение, замена без учёта дат."
    )
    lines.append(
        "- set-by-date — единственное значение во времени, новое заменяет старое только если effective_date ≥ старого."
    )
    lines.append(
        "- add — множественное значение, новые факты добавляются, старые сохраняются."
    )
    lines.append("")

    lines.append("### Практики работы с IRI и литералами")
    lines.append(
        "- **Используй высокоуровневые хелперы билдера**, перечисленные в подсказках "
        "к классам выше (`b.person`, `b.organization`, `b.group`, `b.direction`, "
        "`b.profile`, `b.thesis`, `b.practice`, `b.position`, `b.degree`, `b.title`, "
        "`b.practice_kind`, `b.grade`). Они одной строкой делают типизацию, "
        "идентифицирующие литералы и стабильный IRI — никаких ручных таблиц "
        "перечислений и хеширований из шаблона писать не надо."
    )
    lines.append(
        "- Связи между индивидами добавляй через `b.add_object_property(s, p, o)`. "
        "Для опциональных связей (например, должность сотрудника, которой может не быть) "
        "используй `b.add_object_property_optional(...)` — он молча пропустит триплет "
        "при отсутствии данных, не делая граф невалидным."
    )
    lines.append(
        "- Лямбды и `b.field(...).transform(...)` нужны только для редких случаев, "
        "которых нет в списке хелперов. Если в схеме появился новый стандартный "
        "класс — добавь хелпер в `TemplateGraphBuilder`, а не копируй логику в шаблон."
    )
    lines.append(
        "- Не строй IRI вручную из голой строки с пробелами или кириллицей в свободной форме — "
        "это нарушит детерминизм и приведёт к дубликатам индивидов."
    )

    return "\n".join(lines).rstrip() + "\n"


def _collect_classes(g: Graph) -> Dict[str, _ClassInfo]:
    """Возвращает словарь local_name → _ClassInfo для классов из нашей онтологии."""
    classes: Dict[str, _ClassInfo] = {}

    for s in g.subjects(RDF.type, OWL.Class):
        if not isinstance(s, URIRef) or not str(s).startswith(SUBJECT_NAMESPACE_IRI):
            continue
        local = str(s)[len(SUBJECT_NAMESPACE_IRI):]
        if not local:
            continue

        label = _ru_label(g, s) or local
        comment = _ru_comment(g, s) or ""

        parent_local: Optional[str] = None
        for parent in g.objects(s, RDFS.subClassOf):
            if not isinstance(parent, URIRef):
                continue
            parent_str = str(parent)
            if parent_str.startswith(SUBJECT_NAMESPACE_IRI):
                parent_local = parent_str[len(SUBJECT_NAMESPACE_IRI):]
                break

        classes[local] = _ClassInfo(local, label, comment, parent_local)

    return classes


def _collect_properties(g: Graph) -> Tuple[List[_PropertyInfo], List[_PropertyInfo]]:
    """Возвращает (object_properties, data_properties) — каждое отсортировано по local-name."""
    obj_props: List[_PropertyInfo] = []
    data_props: List[_PropertyInfo] = []

    for prop_type, target in (
        (OWL.ObjectProperty, obj_props),
        (OWL.DatatypeProperty, data_props),
        (OWL.AnnotationProperty, None),
    ):
        if target is None:
            continue
        for s in g.subjects(RDF.type, prop_type):
            if not isinstance(s, URIRef) or not str(s).startswith(SUBJECT_NAMESPACE_IRI):
                continue
            local = str(s)[len(SUBJECT_NAMESPACE_IRI):]
            if not local or local == "mergePolicy":
                continue
            target.append(
                _PropertyInfo(
                    local=local,
                    label=_ru_label(g, s) or local,
                    domain=_short_iri(_first_object(g, s, RDFS.domain)),
                    range=_short_iri(_first_object(g, s, RDFS.range)),
                    policy=_policy_label(_first_object(g, s, _MERGE_POLICY)),
                    comment=_ru_comment(g, s) or "",
                )
            )

    obj_props.sort(key=lambda p: p.local)
    data_props.sort(key=lambda p: p.local)
    return obj_props, data_props


def _collect_enum_individuals(
    g: Graph, classes: Dict[str, _ClassInfo]
) -> Dict[str, List[_IndividualInfo]]:
    """Сгруппированные по классу-перечислению именованные индивиды."""
    by_class: Dict[str, List[_IndividualInfo]] = {}

    for s in g.subjects(RDF.type, OWL.NamedIndividual):
        if not isinstance(s, URIRef) or not str(s).startswith(SUBJECT_NAMESPACE_IRI):
            continue
        local = str(s)[len(SUBJECT_NAMESPACE_IRI):]
        label = _ru_label(g, s) or local

        for typ in g.objects(s, RDF.type):
            if not isinstance(typ, URIRef) or not str(typ).startswith(SUBJECT_NAMESPACE_IRI):
                continue
            typ_local = str(typ)[len(SUBJECT_NAMESPACE_IRI):]
            if typ_local == "NamedIndividual" or typ_local == "MergePolicy":
                continue
            if typ_local not in classes:
                continue
            by_class.setdefault(typ_local, []).append(_IndividualInfo(local, label))

    for items in by_class.values():
        items.sort(key=lambda i: i.local)
    return by_class


def _render_class_tree(classes: Dict[str, _ClassInfo]) -> List[str]:
    children: Dict[Optional[str], List[str]] = {}
    for c in classes.values():
        children.setdefault(c.parent, []).append(c.local)
    for siblings in children.values():
        siblings.sort()

    lines: List[str] = []

    def render(local: str, depth: int):
        info = classes[local]
        indent = "  " * depth
        guide = _IRI_GUIDE.get(local)
        suffix = f"  — IRI: {guide}" if guide else ""
        lines.append(f"{indent}- :{info.local} — «{info.label}»{suffix}")
        for child in children.get(local, []):
            render(child, depth + 1)

    for root_local in children.get(None, []):
        if root_local == "MergePolicy":
            continue
        render(root_local, 0)
    return lines


def _render_enum_individuals(by_class: Dict[str, List[_IndividualInfo]]) -> List[str]:
    if not by_class:
        return ["(перечислений нет)"]
    lines: List[str] = []
    for cls in sorted(by_class.keys()):
        lines.append(f":{cls}:")
        for ind in by_class[cls]:
            lines.append(f"  - :{ind.local}  ({ind.label})")
    return lines


def _render_property_table(props: List[_PropertyInfo]) -> List[str]:
    if not props:
        return ["(нет свойств)"]
    header = "| IRI | label | domain → range | policy |"
    sep = "|---|---|---|---|"
    rows = [header, sep]
    for p in props:
        rows.append(
            f"| :{p.local} | {p.label} | {p.domain} → {p.range} | {p.policy} |"
        )
    return rows


def _ru_label(g: Graph, s: URIRef) -> Optional[str]:
    """Возвращает rdfs:label с предпочтением русского языка."""
    fallback: Optional[str] = None
    for lit in g.objects(s, RDFS.label):
        if not isinstance(lit, Literal):
            continue
        if lit.language == "ru":
            return str(lit)
        if fallback is None:
            fallback = str(lit)
    return fallback


def _ru_comment(g: Graph, s: URIRef) -> Optional[str]:
    fallback: Optional[str] = None
    for lit in g.objects(s, RDFS.comment):
        if not isinstance(lit, Literal):
            continue
        if lit.language == "ru":
            return str(lit)
        if fallback is None:
            fallback = str(lit)
    return fallback


def _first_object(g: Graph, s: URIRef, p: URIRef) -> Optional[URIRef]:
    for o in g.objects(s, p):
        if isinstance(o, URIRef):
            return o
    return None


def _short_iri(node: Optional[URIRef]) -> str:
    if node is None:
        return "—"
    s = str(node)
    if s.startswith(SUBJECT_NAMESPACE_IRI):
        return ":" + s[len(SUBJECT_NAMESPACE_IRI):]
    if s.startswith("http://www.w3.org/2001/XMLSchema#"):
        return "xsd:" + s[len("http://www.w3.org/2001/XMLSchema#"):]
    if s.startswith("http://www.w3.org/2000/01/rdf-schema#"):
        return "rdfs:" + s[len("http://www.w3.org/2000/01/rdf-schema#"):]
    if s.startswith("http://www.w3.org/2002/07/owl#"):
        return "owl:" + s[len("http://www.w3.org/2002/07/owl#"):]
    if s.startswith("http://www.w3.org/1999/02/22-rdf-syntax-ns#"):
        return "rdf:" + s[len("http://www.w3.org/1999/02/22-rdf-syntax-ns#"):]
    return f"<{s}>"


def _policy_label(node: Optional[URIRef]) -> str:
    if node is None:
        return "add (default)"
    s = str(node)
    if not s.startswith(SUBJECT_NAMESPACE_IRI):
        return s
    local = s[len(SUBJECT_NAMESPACE_IRI):]
    return _POLICY_LABELS.get(local, local)


if __name__ == "__main__":
    print(build_schema_summary())
