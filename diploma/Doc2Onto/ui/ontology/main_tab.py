from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QTextEdit, QDialogButtonBox, QHeaderView, QFrame, QMessageBox,
    QSizePolicy, QStackedLayout
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from app.context import get_ontology_repository
from app.settings import SUBJECT_NAMESPACE_IRI


_NS = SUBJECT_NAMESPACE_IRI


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


def predicate_label(g: Graph, p: URIRef) -> str:
    return label_of(g, p) or short_iri(str(p))


def class_label(g: Graph, c: URIRef) -> str:
    return label_of(g, c) or short_iri(str(c))


def is_named_individual(g: Graph, s: URIRef) -> bool:
    return (s, RDF.type, OWL.NamedIndividual) in g


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
    """{class -> [individual]} с учётом подклассов (одна сущность может быть в нескольких классах)."""
    out: Dict[URIRef, List[URIRef]] = {}
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
        out.setdefault(c, []).append(s)
    return out


# =====================================================================
# IndividualCardWidget
# =====================================================================


class IndividualCardWidget(QWidget):
    """Карточка индивида: классы, таблица свойств, входящие ссылки."""

    individual_clicked = Signal(URIRef)
    document_clicked = Signal(str)

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
        self._iri_label.setStyleSheet("color:#888;font-family:monospace;")
        self._iri_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._iri_label.setWordWrap(True)
        layout.addWidget(self._iri_label)

        self._classes_label = QLabel()
        self._classes_label.setWordWrap(True)
        self._classes_label.setStyleSheet("color:#aaa;")
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
                o_item.setForeground(QColor("#90caf9"))
                o_item.setToolTip(short_iri(str(o)) + "\n(клик — перейти)")
                o_item.setData(Qt.ItemDataRole.UserRole, str(o))
            else:
                o_item = QTableWidgetItem(str(o))
                o_item.setData(Qt.ItemDataRole.UserRole, None)
            self._props_table.setItem(r, 1, o_item)

            key = (s.n3(), p.n3(), o.n3())
            ev = journal_index.get(key)
            if ev is not None:
                badge = QTableWidgetItem(f"[1 ист.]")
                badge.setData(Qt.ItemDataRole.UserRole, ev)
                badge.setToolTip("Клик — показать источник")
                badge.setForeground(QColor("#ffd54f"))
            else:
                badge = QTableWidgetItem("—")
                badge.setData(Qt.ItemDataRole.UserRole, None)
                badge.setForeground(QColor("#666"))
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
            s_item.setForeground(QColor("#90caf9"))
            s_item.setData(Qt.ItemDataRole.UserRole, str(s))
            s_item.setToolTip(short_iri(str(s)) + "\n(клик — перейти)")
            self._inbox_table.setItem(r, 0, s_item)
            self._inbox_table.setItem(r, 1, QTableWidgetItem(predicate_label(g, p)))

        self._ttl_button.setVisible(True)

    def _on_props_cell_clicked(self, row: int, col: int):
        if col == 1:
            item = self._props_table.item(row, 1)
            if item is None:
                return
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, str):
                self.individual_clicked.emit(URIRef(data))
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
        if isinstance(data, str):
            self.individual_clicked.emit(URIRef(data))

    def _show_source_popup(self, ev):
        text_lines = [
            f"Документ: {ev.doc_id or '—'}",
            f"Шаблон:   {ev.template_id or '—'}",
            f"Политика: {ev.policy or '—'}",
        ]
        if ev.effective_date:
            text_lines.append(f"Дата факта: {ev.effective_date}")
        if ev.added_at:
            text_lines.append(f"Добавлено: {ev.added_at}")

        dlg = QDialog(self)
        dlg.setWindowTitle("Источник факта")
        dlg.resize(500, 240)
        lay = QVBoxLayout(dlg)
        lab = QLabel("\n".join(text_lines))
        lab.setStyleSheet("font-family:monospace;")
        lay.addWidget(lab)

        if ev.doc_id:
            btn = QPushButton(f"Перейти к документу {ev.doc_id[:8]}…")
            btn.clicked.connect(lambda: (self.document_clicked.emit(ev.doc_id), dlg.accept()))
            lay.addWidget(btn)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        bb.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dlg.accept)
        lay.addWidget(bb)
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
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        bb.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()


# =====================================================================
# OntologyTab
# =====================================================================


class OntologyTab(QWidget):
    """Третья вкладка приложения — навигация по содержимому онтологии."""

    document_navigation_requested = Signal(str)

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
        self._tree.setMinimumWidth(280)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        splitter.addWidget(self._tree)

        self._card = IndividualCardWidget()
        self._card.individual_clicked.connect(self._on_card_individual_clicked)
        self._card.document_clicked.connect(self.document_navigation_requested)
        splitter.addWidget(self._card)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 880])
        layout.addWidget(splitter, 1)

        self.refresh_graph()

    # ------------------------------------------------------------ public

    def refresh_graph(self):
        try:
            assembled = self._repo.assemble_full_graph()
            self._graph = assembled.graph
        except Exception as ex:
            self._graph = None
            QMessageBox.warning(self, "Doc2Onto", f"Не удалось загрузить онтологию: {ex}")

        self._card.set_graph(self._graph)
        self._rebuild_tree()

    # ------------------------------------------------------------ tree

    def _rebuild_tree(self):
        self._tree.clear()
        if self._graph is None:
            return

        g = self._graph
        cls_to_inds = all_classes_with_individuals(g)
        roots = self._tbox_root_classes(g)

        used_classes = set(cls_to_inds.keys())
        relevant_classes = self._collect_class_closure(g, used_classes)

        added: Dict[URIRef, QTreeWidgetItem] = {}
        for root in roots:
            self._add_class_subtree(self._tree.invisibleRootItem(), root, g, cls_to_inds, relevant_classes, added)

        # Добавим классы, корнями не являющиеся, если они не попали никуда
        for c in cls_to_inds:
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

        ind_count = len(cls_to_inds.get(cls, []))
        item = QTreeWidgetItem([f"{class_label(g, cls)} ({ind_count})"])
        item.setData(0, Qt.ItemDataRole.UserRole, ("class", str(cls)))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
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
            ind_item.setData(0, Qt.ItemDataRole.UserRole, ("individual", str(ind)))
            ind_item.setToolTip(0, short_iri(str(ind)))
            item.addChild(ind_item)

    def _on_tree_selection_changed(self):
        items = self._tree.selectedItems()
        if not items:
            self._card.show_individual(None)
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple):
            self._card.show_individual(None)
            return
        kind, iri = data
        if kind == "individual":
            self._card.show_individual(URIRef(iri))
        else:
            self._card.show_individual(None)

    def select_individual(self, iri: URIRef):
        target = str(iri)
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if self._select_descendant(top, target):
                return

    def _select_descendant(self, item: QTreeWidgetItem, target_iri: str) -> bool:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == "individual" and data[1] == target_iri:
            self._tree.setCurrentItem(item)
            return True
        for j in range(item.childCount()):
            if self._select_descendant(item.child(j), target_iri):
                return True
        return False

    def _on_card_individual_clicked(self, iri: URIRef):
        self.select_individual(iri)

    # ------------------------------------------------------------ search

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
