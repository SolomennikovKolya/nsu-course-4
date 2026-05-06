from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QTextEdit, QHeaderView, QFrame, QMessageBox,
    QStackedWidget,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from app.context import get_ontology_repository
from app.settings import SUBJECT_NAMESPACE_IRI
from ui.common.design import (
    UI_COLOR_LINK_CLASS,
    UI_COLOR_LINK_INDIVIDUAL,
    UI_COLOR_TEXT_DIM,
    UI_COLOR_TEXT_MUTED,
    UI_COLOR_TEXT_SECONDARY,
    UI_COLOR_TEXT_SUBTLE,
    MIN_LEFT_PANEL_WIDTH,
    SPLITTER_RATIO_SIZES,
)


_NS = SUBJECT_NAMESPACE_IRI
_META_RDF_TYPES: Set[URIRef] = {
    OWL.Class,
    RDFS.Class,
    OWL.Restriction,
    RDF.Property,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.FunctionalProperty,
    OWL.TransitiveProperty,
}


# =====================================================================
# Helpers
# =====================================================================


def short_iri(iri: str) -> str:
    """Сокращает IRI: либо вырезает префикс _NS как ':', либо возвращает local part."""
    if iri is None:
        return ""
    if iri.startswith(_NS):
        return ":" + iri[len(_NS):]
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    if "/" in iri:
        return iri.rsplit("/", 1)[1]
    return iri


def label_of(g: Graph, node: URIRef, lang: str = "ru") -> Optional[str]:
    """rdfs:label@ru, либо rdfs:label без языка."""
    fallback: Optional[str] = None
    for o in g.objects(node, RDFS.label):
        if isinstance(o, Literal):
            if (o.language or "") == lang:
                return str(o)
            if not o.language and fallback is None:
                fallback = str(o)
    return fallback


def comment_of(g: Graph, node: URIRef, lang: str = "ru") -> Optional[str]:
    """rdfs:comment@ru, либо rdfs:comment без языка."""
    fallback: Optional[str] = None
    for o in g.objects(node, RDFS.comment):
        if isinstance(o, Literal):
            if (o.language or "") == lang:
                return str(o)
            if not o.language and fallback is None:
                fallback = str(o)
    return fallback


def predicate_label(g: Graph, p: URIRef) -> str:
    return label_of(g, p) or short_iri(str(p))


def class_label(g: Graph, c: URIRef) -> str:
    return label_of(g, c) or short_iri(str(c))


def is_named_individual(g: Graph, s: URIRef) -> bool:
    return (s, RDF.type, OWL.NamedIndividual) in g


def is_class(g: Graph, c: URIRef) -> bool:
    """Проверяет, что URIRef объявлен как owl:Class или rdfs:Class в графе."""
    return (c, RDF.type, OWL.Class) in g or (c, RDF.type, RDFS.Class) in g


def is_domain_individual(g: Graph, s: URIRef) -> bool:
    """
    Истинно для «предметного» индивида (ABox), а не для TBox-ресурсов
    вроде классов/свойств/ограничений.
    """
    if is_named_individual(g, s):
        return True
    for t in types_of(g, s):
        if t not in _META_RDF_TYPES:
            return True
    return False


def classify_link_target(g: Graph, node: URIRef) -> Optional[str]:
    """
    Определяет, куда должна вести ссылка из UI: `class`, `individual` или None.

    Приоритет класса выше, чтобы ресурсы, которые объявлены как класс и при этом
    имеют служебные rdf:type, не ошибочно подсвечивались как «индивид».
    """
    if is_class(g, node):
        return "class"
    if is_domain_individual(g, node):
        return "individual"
    return None


def types_of(g: Graph, s: URIRef) -> Set[URIRef]:
    out: Set[URIRef] = set()
    for o in g.objects(s, RDF.type):
        if isinstance(o, URIRef) and o != OWL.NamedIndividual:
            out.add(o)
    return out


def display_name(g: Graph, ind: URIRef, classes: Set[URIRef]) -> str:
    """Человекочитаемое имя индивида."""
    lbl = label_of(g, ind)
    if lbl:
        return lbl

    # Персона: «Фамилия И. О.»
    person_classes = {URIRef(_NS + n) for n in ("Персона", "Студент", "Сотрудник")}
    if classes & person_classes:
        last = first(g, ind, URIRef(_NS + "фамилия"))
        first_name = first(g, ind, URIRef(_NS + "имя"))
        middle = first(g, ind, URIRef(_NS + "отчество"))
        if last:
            parts = [last]
            if first_name:
                parts.append(f"{first_name[:1].upper()}.")
            if middle:
                parts.append(f"{middle[:1].upper()}.")
            return " ".join(parts)

    # Группа
    if URIRef(_NS + "Группа") in classes:
        n = first(g, ind, URIRef(_NS + "номерГруппы"))
        if n:
            return f"Группа {n}"

    # Направление
    if URIRef(_NS + "НаправлениеПодготовки") in classes:
        c = first(g, ind, URIRef(_NS + "кодНаправления"))
        n = first(g, ind, URIRef(_NS + "названиеНаправления"))
        if c and n:
            return f"{c} {n}"
        if c:
            return f"Направление {c}"

    # Профиль
    if URIRef(_NS + "Профиль") in classes:
        n = first(g, ind, URIRef(_NS + "названиеПрофиля"))
        if n:
            return n

    # Организация
    org_classes = {URIRef(_NS + n) for n in
                   ("Организация", "Университет", "СтруктурноеПодразделение",
                    "Факультет", "Кафедра", "Лаборатория", "ВнешняяОрганизация")}
    if classes & org_classes:
        for o in g.objects(ind, URIRef(_NS + "названиеОрганизации")):
            if isinstance(o, Literal):
                return str(o)

    # ВКР: тема
    if URIRef(_NS + "ВКР") in classes:
        n = first(g, ind, URIRef(_NS + "темаВКР"))
        if n:
            return f"ВКР: {n[:60]}"

    return short_iri(str(ind))


def first(g: Graph, s: URIRef, p: URIRef) -> Optional[str]:
    for o in g.objects(s, p):
        if isinstance(o, Literal):
            return str(o)
    return None


def collect_classes_with_subclasses(g: Graph) -> List[URIRef]:
    """Все классы, кроме owl:NamedIndividual."""
    out: Set[URIRef] = set()
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            out.add(s)
    return sorted(out, key=lambda c: class_label(g, c))


def class_hierarchy(g: Graph) -> Dict[URIRef, List[URIRef]]:
    """Возвращает {parent -> [children]} (только direct subClassOf)."""
    children: Dict[URIRef, List[URIRef]] = {}
    for s, _, o in g.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            children.setdefault(o, []).append(s)
    return children


def all_classes_with_individuals(g: Graph) -> Dict[URIRef, List[URIRef]]:
    """
    Возвращает отображение ``{класс -> [индивиды]}`` для дерева навигации.

    Важно: если индивид типизирован сразу и базовым классом, и его подклассом
    (например, :Персона + :Студент), в дереве он показывается только в наиболее
    «узком» классе (:Студент). При этом множественная принадлежность к
    независимым классам (без отношения subClassOf) сохраняется.
    """
    raw_by_individual: Dict[URIRef, Set[URIRef]] = {}

    for s, _, c in g.triples((None, RDF.type, None)):
        if not isinstance(s, URIRef) or not isinstance(c, URIRef):
            continue
        if c == OWL.NamedIndividual:
            continue
        if c == OWL.Class or c == OWL.Restriction or c == RDF.Property \
           or c == OWL.ObjectProperty or c == OWL.DatatypeProperty \
           or c == OWL.AnnotationProperty or c == OWL.FunctionalProperty \
           or c == OWL.TransitiveProperty:
            continue
        raw_by_individual.setdefault(s, set()).add(c)

    subclass_memo: Dict[Tuple[URIRef, URIRef], bool] = {}

    def is_strict_subclass_of(child: URIRef, parent: URIRef) -> bool:
        if child == parent:
            return False
        key = (child, parent)
        cached = subclass_memo.get(key)
        if cached is not None:
            return cached

        stack = [child]
        seen: Set[URIRef] = set()
        found = False
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for sup in g.objects(cur, RDFS.subClassOf):
                if not isinstance(sup, URIRef):
                    continue
                if sup == parent:
                    found = True
                    break
                stack.append(sup)
            if found:
                break

        subclass_memo[key] = found
        return found

    out: Dict[URIRef, List[URIRef]] = {}
    for ind, classes in raw_by_individual.items():
        minimal_classes: Set[URIRef] = set()
        for c in classes:
            # Убираем только те классы, для которых есть более конкретный тип
            # этого же индивида в рамках иерархии subClassOf.
            overshadowed = any(
                other != c and is_strict_subclass_of(other, c)
                for other in classes
            )
            if not overshadowed:
                minimal_classes.add(c)

        for c in minimal_classes:
            out.setdefault(c, []).append(ind)

    return out


# =====================================================================
# SourceFactDialog
# =====================================================================


class SourceFactDialog(QDialog):
    """
    Модальное окно «Источник факта»: показывает doc/template/policy/даты для триплета
    и предлагает кнопки перехода к документу и к шаблону.

    Само окно закрывается крестиком — нативной кнопки Close в layout нет.
    """

    document_requested = Signal(str)
    template_requested = Signal(str)

    def __init__(self, ev, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Источник факта")

        text_lines = [
            f"Документ: {ev.doc_id or '—'}",
            f"Шаблон:   {ev.template_id or '—'}",
            f"Политика: {ev.policy or '—'}",
        ]
        if ev.effective_date:
            text_lines.append(f"Дата факта: {ev.effective_date}")
        if ev.added_at:
            text_lines.append(f"Добавлено: {ev.added_at}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        info_label = QLabel("\n".join(text_lines))
        info_label.setStyleSheet("font-family:monospace;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_label.setWordWrap(False)
        layout.addWidget(info_label)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        if ev.doc_id:
            doc_btn = QPushButton(f"Перейти к документу")
            doc_btn.clicked.connect(lambda: self._on_navigate(ev.doc_id, self.document_requested))
            buttons_row.addWidget(doc_btn)

        if ev.template_id:
            tpl_btn = QPushButton(f"Перейти к шаблону")
            tpl_btn.clicked.connect(lambda: self._on_navigate(ev.template_id, self.template_requested))
            buttons_row.addWidget(tpl_btn)

        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        # Прижимаем содержимое к верху — оставшееся место уходит вниз.
        layout.addStretch(1)

    def _on_navigate(self, target_id: str, signal: Signal):
        signal.emit(target_id)
        self.accept()


# =====================================================================
# IndividualCardWidget
# =====================================================================


class IndividualCardWidget(QWidget):
    """Карточка индивида: классы, таблица свойств, входящие ссылки."""

    individual_clicked = Signal(URIRef)
    class_clicked = Signal(URIRef)
    document_clicked = Signal(str)
    template_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self._graph: Optional[Graph] = None
        self._iri: Optional[URIRef] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-size:18px;font-weight:bold;")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._iri_label = QLabel()
        self._iri_label.setStyleSheet(f"color:{UI_COLOR_TEXT_MUTED};font-family:monospace;")
        self._iri_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._iri_label.setWordWrap(True)
        layout.addWidget(self._iri_label)

        self._classes_label = QLabel()
        self._classes_label.setWordWrap(True)
        self._classes_label.setStyleSheet(f"color:{UI_COLOR_TEXT_SUBTLE};")
        layout.addWidget(self._classes_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        layout.addWidget(QLabel("Свойства:"))
        self._props_table = QTableWidget(0, 3)
        self._props_table.setHorizontalHeaderLabels(["Предикат", "Объект", "Источники"])
        self._props_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._props_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._props_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._props_table.cellClicked.connect(self._on_props_cell_clicked)
        layout.addWidget(self._props_table, 1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        layout.addWidget(QLabel("Входящие ссылки:"))
        self._inbox_table = QTableWidget(0, 2)
        self._inbox_table.setHorizontalHeaderLabels(["Субъект", "Предикат"])
        self._inbox_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._inbox_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._inbox_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._inbox_table.cellClicked.connect(self._on_inbox_cell_clicked)
        layout.addWidget(self._inbox_table, 1)

        self._ttl_button = QPushButton("Показать TTL")
        self._ttl_button.clicked.connect(self._on_show_ttl)
        layout.addWidget(self._ttl_button)

        self.set_graph(None)

    def set_graph(self, graph: Optional[Graph]):
        self._graph = graph
        self.show_individual(None)

    def show_individual(self, iri: Optional[URIRef]):
        self._iri = iri
        if self._graph is None or iri is None:
            self._title_label.setText("Выберите индивид")
            self._iri_label.setText("")
            self._classes_label.setText("")
            self._props_table.setRowCount(0)
            self._inbox_table.setRowCount(0)
            self._ttl_button.setVisible(False)
            return

        g = self._graph
        classes = sorted(types_of(g, iri), key=lambda c: class_label(g, c))
        self._title_label.setText(display_name(g, iri, set(classes)))
        self._iri_label.setText(short_iri(str(iri)) + "  (" + str(iri) + ")")

        if classes:
            self._classes_label.setText("Класс(ы): " + ", ".join(class_label(g, c) for c in classes))
        else:
            self._classes_label.setText("")

        # --- свойства ---
        repo = get_ontology_repository()
        journal_index = repo.journal_active_facts_index()

        # фильтр: оставляем триплеты, где subject = iri, исключая rdf:type owl:NamedIndividual
        rows: List[Tuple[URIRef, URIRef, object]] = []
        for s, p, o in g.triples((iri, None, None)):
            if p == RDF.type and o == OWL.NamedIndividual:
                continue
            rows.append((s, p, o))

        rows.sort(key=lambda t: (predicate_label(g, t[1]), str(t[2])))
        self._props_table.setRowCount(len(rows))

        for r, (s, p, o) in enumerate(rows):
            p_label = predicate_label(g, p)
            p_item = QTableWidgetItem(p_label)
            p_item.setToolTip(short_iri(str(p)))
            self._props_table.setItem(r, 0, p_item)

            if isinstance(o, URIRef):
                o_text = display_name(g, o, types_of(g, o))
                o_item = QTableWidgetItem(o_text)
                # Различаем визуально индивиды и классы — это снимает прежнюю
                # путаницу, когда у класса показывался tooltip «клик — перейти»,
                # а на деле клик ничего не делал.
                target_kind = classify_link_target(g, o)
                if target_kind == "individual":
                    o_item.setForeground(QColor(UI_COLOR_LINK_INDIVIDUAL))
                    o_item.setToolTip(short_iri(str(o)) + "\n(клик — перейти к индивиду)")
                    o_item.setData(Qt.ItemDataRole.UserRole, ("individual", str(o)))
                elif target_kind == "class":
                    o_item.setForeground(QColor(UI_COLOR_LINK_CLASS))
                    o_item.setToolTip(short_iri(str(o)) + "\n(клик — перейти к классу)")
                    o_item.setData(Qt.ItemDataRole.UserRole, ("class", str(o)))
                else:
                    o_item.setToolTip(short_iri(str(o)))
                    o_item.setData(Qt.ItemDataRole.UserRole, None)
            else:
                o_item = QTableWidgetItem(str(o))
                o_item.setData(Qt.ItemDataRole.UserRole, None)
            self._props_table.setItem(r, 1, o_item)

            key = (s.n3(), p.n3(), o.n3())
            ev = journal_index.get(key)
            if ev is not None:
                badge = QTableWidgetItem(f"[ист.]")
                badge.setData(Qt.ItemDataRole.UserRole, ev)
                badge.setToolTip("Клик — показать источник")
            else:
                badge = QTableWidgetItem("—")
                badge.setData(Qt.ItemDataRole.UserRole, None)
                badge.setForeground(QColor(UI_COLOR_TEXT_DIM))
            self._props_table.setItem(r, 2, badge)

        # --- входящие ---
        inrows: List[Tuple[URIRef, URIRef]] = []
        for s, p, o in g.triples((None, None, iri)):
            if isinstance(s, URIRef) and isinstance(p, URIRef):
                inrows.append((s, p))
        inrows.sort(key=lambda t: (predicate_label(g, t[1]), str(t[0])))
        self._inbox_table.setRowCount(len(inrows))
        for r, (s, p) in enumerate(inrows):
            s_text = display_name(g, s, types_of(g, s))
            s_item = QTableWidgetItem(s_text)
            target_kind = classify_link_target(g, s)
            if target_kind == "individual":
                s_item.setForeground(QColor(UI_COLOR_LINK_INDIVIDUAL))
                s_item.setData(Qt.ItemDataRole.UserRole, ("individual", str(s)))
                s_item.setToolTip(short_iri(str(s)) + "\n(клик — перейти к индивиду)")
            elif target_kind == "class":
                s_item.setForeground(QColor(UI_COLOR_LINK_CLASS))
                s_item.setData(Qt.ItemDataRole.UserRole, ("class", str(s)))
                s_item.setToolTip(short_iri(str(s)) + "\n(клик — перейти к классу)")
            else:
                s_item.setData(Qt.ItemDataRole.UserRole, None)
                s_item.setToolTip(short_iri(str(s)))
            self._inbox_table.setItem(r, 0, s_item)
            self._inbox_table.setItem(r, 1, QTableWidgetItem(predicate_label(g, p)))

        self._ttl_button.setVisible(True)

    def _on_props_cell_clicked(self, row: int, col: int):
        if col == 1:
            item = self._props_table.item(row, 1)
            if item is None:
                return
            data = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(data, tuple):
                return
            kind, iri = data
            if kind == "individual":
                self.individual_clicked.emit(URIRef(iri))
            elif kind == "class":
                self.class_clicked.emit(URIRef(iri))
        elif col == 2:
            item = self._props_table.item(row, 2)
            if item is None:
                return
            ev = item.data(Qt.ItemDataRole.UserRole)
            if ev is None:
                return
            self._show_source_popup(ev)

    def _on_inbox_cell_clicked(self, row: int, col: int):
        if col != 0:
            return
        item = self._inbox_table.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple):
            kind, iri = data
            if kind == "individual":
                self.individual_clicked.emit(URIRef(iri))
            elif kind == "class":
                self.class_clicked.emit(URIRef(iri))

    def _show_source_popup(self, ev):
        dlg = SourceFactDialog(ev, self)
        dlg.document_requested.connect(self.document_clicked)
        dlg.template_requested.connect(self.template_clicked)
        dlg.exec()

    def _on_show_ttl(self):
        if self._graph is None or self._iri is None:
            return
        sub = Graph()
        for s, p, o in self._graph.triples((self._iri, None, None)):
            sub.add((s, p, o))
        for s, p, o in self._graph.triples((None, None, self._iri)):
            sub.add((s, p, o))
        try:
            sub.bind("", _NS)
        except Exception:
            pass
        text = sub.serialize(format="turtle")
        if isinstance(text, bytes):
            text = text.decode("utf-8")

        dlg = QDialog(self)
        dlg.setWindowTitle("TTL")
        dlg.resize(800, 600)
        lay = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        view.setStyleSheet("font-family:monospace;")
        lay.addWidget(view)
        dlg.exec()


# =====================================================================
# ClassCardWidget
# =====================================================================


class ClassCardWidget(QWidget):
    """
    Карточка класса: label, IRI, comment, родительские/дочерние классы,
    список индивидов этого класса (с кликом-навигацией). Появляется,
    когда в дереве выбран класс, а не индивид, либо когда пользователь
    кликнул на ссылку-класс в карточке индивида.
    """

    class_clicked = Signal(URIRef)
    individual_clicked = Signal(URIRef)

    def __init__(self):
        super().__init__()
        self._graph: Optional[Graph] = None
        self._iri: Optional[URIRef] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-size:18px;font-weight:bold;")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._iri_label = QLabel()
        self._iri_label.setStyleSheet(f"color:{UI_COLOR_TEXT_MUTED};font-family:monospace;")
        self._iri_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._iri_label.setWordWrap(True)
        layout.addWidget(self._iri_label)

        self._parents_label = QLabel()
        self._parents_label.setWordWrap(True)
        self._parents_label.setStyleSheet(f"color:{UI_COLOR_TEXT_SUBTLE};")
        layout.addWidget(self._parents_label)

        self._comment_label = QLabel()
        self._comment_label.setWordWrap(True)
        self._comment_label.setStyleSheet(f"color:{UI_COLOR_TEXT_SECONDARY};")
        self._comment_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._comment_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        layout.addWidget(QLabel("Подклассы:"))
        self._subclasses_table = QTableWidget(0, 1)
        self._subclasses_table.setHorizontalHeaderLabels(["Класс"])
        self._subclasses_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._subclasses_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._subclasses_table.cellClicked.connect(self._on_subclasses_cell_clicked)
        layout.addWidget(self._subclasses_table, 1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        self._individuals_header = QLabel("Индивиды:")
        layout.addWidget(self._individuals_header)
        self._individuals_table = QTableWidget(0, 1)
        self._individuals_table.setHorizontalHeaderLabels(["Индивид"])
        self._individuals_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._individuals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._individuals_table.cellClicked.connect(self._on_individuals_cell_clicked)
        layout.addWidget(self._individuals_table, 2)

    def set_graph(self, graph: Optional[Graph]):
        self._graph = graph

    def show_class(self, iri: URIRef):
        self._iri = iri
        g = self._graph
        if g is None:
            return

        self._title_label.setText(class_label(g, iri))
        self._iri_label.setText(short_iri(str(iri)) + "  (" + str(iri) + ")")

        parents = sorted(
            (p for p in g.objects(iri, RDFS.subClassOf) if isinstance(p, URIRef)),
            key=lambda c: class_label(g, c),
        )
        if parents:
            self._parents_label.setText(
                "Подкласс: " + ", ".join(class_label(g, p) for p in parents)
            )
        else:
            self._parents_label.setText("")

        comment = comment_of(g, iri)
        if comment:
            self._comment_label.setText(comment)
            self._comment_label.setVisible(True)
        else:
            self._comment_label.setText("")
            self._comment_label.setVisible(False)

        # Подклассы
        subclasses = sorted(
            (s for s, _, _ in g.triples((None, RDFS.subClassOf, iri)) if isinstance(s, URIRef)),
            key=lambda c: class_label(g, c),
        )
        self._subclasses_table.setRowCount(len(subclasses))
        for r, sub in enumerate(subclasses):
            item = QTableWidgetItem(class_label(g, sub))
            item.setForeground(QColor(UI_COLOR_LINK_CLASS))
            item.setData(Qt.ItemDataRole.UserRole, str(sub))
            item.setToolTip(short_iri(str(sub)) + "\n(клик — перейти)")
            self._subclasses_table.setItem(r, 0, item)

        # Индивиды (с учётом подклассов в TBox: считаем только direct rdf:type)
        directs: List[URIRef] = []
        for s, _, o in g.triples((None, RDF.type, iri)):
            if isinstance(s, URIRef):
                directs.append(s)
        directs.sort(key=lambda i: display_name(g, i, types_of(g, i)).lower())

        self._individuals_header.setText(f"Индивиды ({len(directs)}):")
        self._individuals_table.setRowCount(len(directs))
        for r, ind in enumerate(directs):
            item = QTableWidgetItem(display_name(g, ind, types_of(g, ind)))
            item.setForeground(QColor(UI_COLOR_LINK_INDIVIDUAL))
            item.setData(Qt.ItemDataRole.UserRole, str(ind))
            item.setToolTip(short_iri(str(ind)) + "\n(клик — перейти)")
            self._individuals_table.setItem(r, 0, item)

    def _on_subclasses_cell_clicked(self, row: int, _col: int):
        item = self._subclasses_table.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, str):
            self.class_clicked.emit(URIRef(data))

    def _on_individuals_cell_clicked(self, row: int, _col: int):
        item = self._individuals_table.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, str):
            self.individual_clicked.emit(URIRef(data))


# =====================================================================
# OntologyTab
# =====================================================================


class OntologyTab(QWidget):
    """Третья вкладка приложения — навигация по содержимому онтологии."""

    document_navigation_requested = Signal(str)
    template_navigation_requested = Signal(str)

    # Индексы страниц в правом стэке: empty / class / individual.
    _PAGE_EMPTY = 0
    _PAGE_CLASS = 1
    _PAGE_INDIVIDUAL = 2

    def __init__(self):
        super().__init__()
        self._repo = get_ontology_repository()
        self._graph: Optional[Graph] = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._apply_filter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск по литералам и фрагменту IRI...")
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(MIN_LEFT_PANEL_WIDTH)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        splitter.addWidget(self._tree)

        # Правый стэк — три страницы: пусто / класс / индивид.
        self._stack = QStackedWidget()

        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(12, 12, 12, 12)
        empty_label = QLabel("Выберите класс или индивид")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet(f"color:{UI_COLOR_TEXT_MUTED};")
        empty_layout.addWidget(empty_label)
        self._stack.addWidget(empty_page)

        self._class_card = ClassCardWidget()
        self._class_card.class_clicked.connect(self._on_class_link_clicked)
        self._class_card.individual_clicked.connect(self._on_card_individual_clicked)
        self._stack.addWidget(self._class_card)

        self._individual_card = IndividualCardWidget()
        self._individual_card.individual_clicked.connect(self._on_card_individual_clicked)
        self._individual_card.class_clicked.connect(self._on_class_link_clicked)
        self._individual_card.document_clicked.connect(self.document_navigation_requested)
        self._individual_card.template_clicked.connect(self.template_navigation_requested)
        self._stack.addWidget(self._individual_card)

        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(SPLITTER_RATIO_SIZES)
        layout.addWidget(splitter, 1)

        self.refresh_graph()

    # ---------- public ----------

    def refresh_graph(self):
        try:
            assembled = self._repo.assemble_full_graph()
            self._graph = assembled.graph
        except Exception as ex:
            self._graph = None
            QMessageBox.warning(self, "Doc2Onto", f"Не удалось загрузить онтологию: {ex}")

        self._individual_card.set_graph(self._graph)
        self._class_card.set_graph(self._graph)
        self._stack.setCurrentIndex(self._PAGE_EMPTY)
        self._rebuild_tree()

    # ---------- tree ----------

    def _rebuild_tree(self):
        self._tree.clear()
        if self._graph is None:
            return

        g = self._graph
        cls_to_inds = all_classes_with_individuals(g)
        all_classes = set(collect_classes_with_subclasses(g))
        roots = self._tbox_root_classes(g)
        relevant_classes = all_classes

        added: Dict[URIRef, QTreeWidgetItem] = {}
        for root in roots:
            self._add_class_subtree(self._tree.invisibleRootItem(), root, g, cls_to_inds, relevant_classes, added)

        # Добавим классы, не попавшие в обход от корней (на случай "рваной" TBox).
        for c in sorted(relevant_classes, key=lambda x: class_label(g, x)):
            if c not in added:
                self._add_class_subtree(self._tree.invisibleRootItem(), c, g, cls_to_inds, relevant_classes, added)

        self._tree.expandAll()
        self._apply_filter()

    @staticmethod
    def _tbox_root_classes(g: Graph) -> List[URIRef]:
        all_cls: Set[URIRef] = set()
        for s in g.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                all_cls.add(s)
        for s in g.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                all_cls.add(s)
        non_roots: Set[URIRef] = set()
        for s, _, o in g.triples((None, RDFS.subClassOf, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                non_roots.add(s)
        return sorted(all_cls - non_roots, key=lambda c: class_label(g, c))

    def _collect_class_closure(self, g: Graph, used: Set[URIRef]) -> Set[URIRef]:
        """Включает в результат все used и их супер-классы."""
        out: Set[URIRef] = set(used)
        added = True
        while added:
            added = False
            for s, _, o in g.triples((None, RDFS.subClassOf, None)):
                if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                    continue
                if s in out and o not in out:
                    out.add(o)
                    added = True
        return out

    def _add_class_subtree(
        self,
        parent: QTreeWidgetItem,
        cls: URIRef,
        g: Graph,
        cls_to_inds: Dict[URIRef, List[URIRef]],
        relevant: Set[URIRef],
        added: Dict[URIRef, QTreeWidgetItem],
    ):
        if cls in added:
            return

        # subclass children
        children: List[URIRef] = []
        for s, _, o in g.triples((None, RDFS.subClassOf, cls)):
            if isinstance(s, URIRef) and (s in relevant or s in cls_to_inds):
                children.append(s)
        children.sort(key=lambda c: class_label(g, c))

        item = QTreeWidgetItem([class_label(g, cls)])
        item.setForeground(0, QColor(UI_COLOR_LINK_CLASS))
        item.setData(0, Qt.ItemDataRole.UserRole, ("class", str(cls)))
        # Класс остаётся выбираемым — теперь у него есть собственная карточка.
        parent.addChild(item)
        added[cls] = item

        for sub in children:
            self._add_class_subtree(item, sub, g, cls_to_inds, relevant, added)

        # Индивиды этого класса
        inds = cls_to_inds.get(cls, [])
        sortable: List[Tuple[str, URIRef]] = []
        for ind in inds:
            sortable.append((display_name(g, ind, types_of(g, ind)).lower(), ind))
        sortable.sort(key=lambda t: t[0])
        for _, ind in sortable:
            ind_item = QTreeWidgetItem([display_name(g, ind, types_of(g, ind))])
            ind_item.setForeground(0, QColor(UI_COLOR_LINK_INDIVIDUAL))
            ind_item.setData(0, Qt.ItemDataRole.UserRole, ("individual", str(ind)))
            ind_item.setToolTip(0, short_iri(str(ind)))
            item.addChild(ind_item)

    def _on_tree_selection_changed(self):
        items = self._tree.selectedItems()
        if not items:
            self._stack.setCurrentIndex(self._PAGE_EMPTY)
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple):
            self._stack.setCurrentIndex(self._PAGE_EMPTY)
            return
        kind, iri = data
        if kind == "individual":
            self._individual_card.show_individual(URIRef(iri))
            self._stack.setCurrentIndex(self._PAGE_INDIVIDUAL)
        elif kind == "class":
            self._class_card.show_class(URIRef(iri))
            self._stack.setCurrentIndex(self._PAGE_CLASS)
        else:
            self._stack.setCurrentIndex(self._PAGE_EMPTY)

    def select_individual(self, iri: URIRef):
        target = str(iri)
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if self._select_descendant(top, target, kind="individual"):
                return

    def select_class(self, iri: URIRef):
        target = str(iri)
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if self._select_descendant(top, target, kind="class"):
                return

    def _select_descendant(self, item: QTreeWidgetItem, target_iri: str, *, kind: str) -> bool:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == kind and data[1] == target_iri:
            self._tree.setCurrentItem(item)
            return True
        for j in range(item.childCount()):
            if self._select_descendant(item.child(j), target_iri, kind=kind):
                return True
        return False

    def _on_card_individual_clicked(self, iri: URIRef):
        self.select_individual(iri)

    def _on_class_link_clicked(self, iri: URIRef):
        self.select_class(iri)

    # ---------- search ----------

    def _on_search_changed(self, _text: str):
        self._search_timer.start()

    def _apply_filter(self):
        text = (self._search.text() or "").strip().lower()

        def visit(item: QTreeWidgetItem) -> bool:
            self_ok = text == "" or text in item.text(0).lower()

            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple) and data[0] == "individual" and self._graph is not None:
                self_ok = self_ok or text in str(data[1]).lower() or self._individual_matches(URIRef(data[1]), text)

            child_ok = False
            for j in range(item.childCount()):
                if visit(item.child(j)):
                    child_ok = True

            visible = self_ok or child_ok
            item.setHidden(not visible)
            return visible

        for i in range(self._tree.topLevelItemCount()):
            visit(self._tree.topLevelItem(i))

    def _individual_matches(self, iri: URIRef, text: str) -> bool:
        if self._graph is None or text == "":
            return True
        for _, _, o in self._graph.triples((iri, None, None)):
            if isinstance(o, Literal) and text in str(o).lower():
                return True
        return False
