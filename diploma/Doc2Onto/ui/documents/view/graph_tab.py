from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD
from rdflib.util import from_n3

from app.settings import SUBJECT_NAMESPACE_IRI
from core.graph.draft_graph import DraftGraph, DraftNode, DraftTriple, EditedGraph
from models.document import Document
from modules.extractor import ExtractionResult
from modules.validator import ValidationResult
from ui.common.design import UI_COLOR_GRAY, UI_COLOR_GREEN, UI_COLOR_RED, UI_COLOR_YELLOW
from ui.documents.view.common import read_text_file, wrap_tab_page_content


def _warn_color(level: int) -> str:
    if level <= 0:
        return UI_COLOR_GREEN
    if level == 1:
        return UI_COLOR_YELLOW
    return UI_COLOR_RED


def _node_row_warn_level(node: DraftNode) -> int:
    if node.is_complete():
        return 0
    if node.error is not None or node.source is not None:
        return 1
    return 2


def _triple_badge_warn_level_nodes(s: DraftNode, p: DraftNode, o: DraftNode) -> int:
    if s.is_complete() and p.is_complete() and o.is_complete():
        return 0
    if not s.is_complete() and not p.is_complete() and not o.is_complete():
        return 2
    return 1


def _make_prefix_graph() -> Graph:
    g = Graph()
    g.bind("", Namespace(SUBJECT_NAMESPACE_IRI))
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    return g


def _term_n3_short(nm_graph: Graph, term: object) -> str:
    if term is None:
        return "—"
    if isinstance(term, (URIRef, Literal)):
        return term.n3(nm_graph.namespace_manager)
    return str(term)


def _draft_node_from_n3_input(kind: DraftNode.Type, n3_text: str, source: Optional[str]) -> DraftNode:
    t = (n3_text or "").strip()
    if not t or t == "—":
        return DraftNode(kind, None, None, source)
    try:
        parsed = from_n3(t)
        if kind == DraftNode.Type.IRI and not isinstance(parsed, URIRef):
            return DraftNode(kind, None, "ожидался IRI", source)
        if kind == DraftNode.Type.LITERAL and not isinstance(parsed, Literal):
            return DraftNode(kind, None, "ожидался литерал", source)
        return DraftNode(kind, parsed, None, source)
    except Exception as ex:
        return DraftNode(kind, None, str(ex), source)


def _effective_node(edited: EditedGraph, triple_index: int, role: str) -> DraftNode:
    tr = edited.draft.triples[triple_index]
    return edited.node_overrides.get((triple_index, role), tr.get_node(role))


class _NodeDetailBlock(QGroupBox):
    """Один столбец «извлечение» / «валидация» / «сборка»."""

    def __init__(self, title: str, warn_level: int, lines: List[Tuple[str, str]]):
        super().__init__(title)
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; color: {_warn_color(warn_level)}; }}"
        )
        lay = QVBoxLayout(self)
        for label, value in lines:
            row = QVBoxLayout()
            row.addWidget(QLabel(f"<b>{label}</b>"))
            v = QLabel(value if value else "—")
            v.setWordWrap(True)
            row.addWidget(v)
            lay.addLayout(row)


class _TripleRowWidget(QFrame):
    """Плашка одного триплета: свёрнутое резюме и развёрнутое редактирование."""

    def __init__(
        self,
        triple_index: int,
        edited: EditedGraph,
        nm_graph: Graph,
        extraction: Optional[ExtractionResult],
        validation: Optional[ValidationResult],
        on_changed: Callable[[], None],
    ):
        super().__init__()
        self.triple_index = triple_index
        self.edited = edited
        self.nm_graph = nm_graph
        self.extraction = extraction
        self.validation = validation
        self.on_changed = on_changed

        self._expanded = False
        self.setFrameShape(QFrame.Shape.StyledPanel)

        tr = edited.draft.triples[triple_index]
        self._triple_type = tr.triple_type

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        head = QHBoxLayout()
        self._stripe = QFrame()
        self._stripe.setFixedWidth(6)
        head.addWidget(self._stripe)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")
        self._summary.setFont(mono)
        head.addWidget(self._summary, stretch=1)

        self._toggle = QPushButton("▼")
        self._toggle.setFixedWidth(28)
        self._toggle.clicked.connect(self._on_toggle)
        head.addWidget(self._toggle)

        outer.addLayout(head)

        self._body = QWidget()
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(0, 8, 0, 0)

        self._exclude_btn = QPushButton()
        self._exclude_btn.clicked.connect(self._on_toggle_exclude)
        body_lay.addWidget(self._exclude_btn)

        self._role_rows: Dict[str, Tuple[QLineEdit, QWidget, QPushButton, QWidget]] = {}

        for role, title in (("subject", "Субъект"), ("predicate", "Предикат"), ("object", "Объект")):
            role_fr = QFrame()
            role_fr.setFrameShape(QFrame.Shape.StyledPanel)
            rl = QVBoxLayout(role_fr)

            cap = QHBoxLayout()
            cap_lbl = QLabel(title)
            cap.addWidget(cap_lbl)
            stripe = QFrame()
            stripe.setFixedWidth(4)
            cap.insertWidget(0, stripe)

            edit = QLineEdit()
            edit.setFont(mono)
            det_toggle = QPushButton("Подробнее …")
            det_toggle.setCheckable(True)
            det_toggle.setChecked(False)
            details = QWidget()
            det_lay = QVBoxLayout(details)
            det_lay.setContentsMargins(8, 4, 8, 4)
            details.setVisible(False)

            inner_details = QWidget()
            inner_details.setLayout(QVBoxLayout())
            det_lay.addWidget(inner_details)

            def on_detail_toggled(
                checked: bool,
                r: str = role,
                st: QPushButton = det_toggle,
                det: QWidget = details,
            ):
                det.setVisible(checked)
                st.setText("Скрыть" if checked else "Подробнее …")
                if checked:
                    self._fill_details(r, inner_details)

            det_toggle.toggled.connect(on_detail_toggled)

            rl.addLayout(cap)
            rl.addWidget(edit)

            rl.addWidget(det_toggle)
            rl.addWidget(details)
            body_lay.addWidget(role_fr)

            self._role_rows[role] = (edit, stripe, det_toggle, inner_details)

        outer.addWidget(self._body)
        self._body.setVisible(False)

        self.refresh()

    def _on_toggle(self):
        if self._expanded:
            self.apply_edits()
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle.setText("▲" if self._expanded else "▼")
        if self._expanded:
            self._populate_edits()

    def _on_toggle_exclude(self):
        idx = self.triple_index
        if idx in self.edited.excluded:
            self.edited.include_triple(idx)
        else:
            self.edited.exclude_triple(idx)
        self.on_changed()

    def _populate_edits(self):
        for role, (edit, _, _, inner) in self._role_rows.items():
            node = _effective_node(self.edited, self.triple_index, role)
            n3 = node._to_json_dict().get("n3") or ""
            edit.setText(n3)
            self._fill_details(role, inner)

    def _fill_details(self, role: str, inner: QWidget):
        lay = inner.layout()
        if lay is not None:
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
                    continue
                sub = item.layout()
                if sub is not None:
                    while sub.count():
                        it2 = sub.takeAt(0)
                        if it2.widget() is not None:
                            it2.widget().deleteLater()
                    sub.deleteLater()

        node = _effective_node(self.edited, self.triple_index, role)
        field = node.source

        # --- извлечение ---
        ex_lines: List[Tuple[str, str]] = []
        ex_level = 1
        if self.extraction is None or not field:
            ex_lines = [("Статус", "нет привязки к полю" if not field else "нет данных извлечения")]
            ex_level = 1
        else:
            data = self.extraction.get_field(field)
            if data:
                sit = self.extraction.get_situation(field)
                ex_level = sit.warn_level()
                ex_lines.append(("Ситуация", sit.short_msg()))
                ex_lines.append(("Шаблон: извлечено", "да" if data.get("extracted_temp") else "нет"))
                ex_lines.append(("Шаблон: значение", data.get("value_temp") or "—"))
                ex_lines.append(("Шаблон: ошибка", data.get("error_temp") or "—"))
                if data.get("extracted_llm") is not None:
                    ex_lines.append(("LLM: извлечено", "да" if data.get("extracted_llm") else "нет"))
                    ex_lines.append(("LLM: значение", data.get("value_llm") or "—"))
                    ex_lines.append(("LLM: ошибка", data.get("error_llm") or "—"))
            else:
                ex_lines.append(("Статус", "поле не найдено в результате извлечения"))
                ex_level = 2

        # --- валидация ---
        va_lines: List[Tuple[str, str]] = []
        va_level = 1
        if self.validation is None or not field:
            va_lines = [("Статус", "нет привязки к полю" if not field else "нет данных валидации")]
            va_level = 1
        else:
            vdata = self.validation.get_field(field)
            if vdata:
                vsit = self.validation.get_situation(field)
                va_level = vsit.warn_level()
                va_lines.append(("Ситуация", vsit.short_msg()))
                va_lines.append(("Шаблон: валидно", "да" if vdata.get("valid_temp") else "нет"))
                va_lines.append(("Шаблон: ошибка", vdata.get("error_temp") or "—"))
                if vdata.get("valid_llm") is not None:
                    va_lines.append(("LLM: валидно", "да" if vdata.get("valid_llm") else "нет"))
                    va_lines.append(("LLM: ошибка", vdata.get("error_llm") or "—"))
            else:
                va_lines.append(("Статус", "поле не найдено в результате валидации"))
                va_level = 2

        # --- сборка ---
        asm_level = _node_row_warn_level(node)
        asm_lines = [
            ("Тип", node.type.name),
            ("Значение (n3)", node._to_json_dict().get("n3") or "—"),
            ("Ошибка", str(node.error) if node.error else "—"),
            ("Источник", node.source or "—"),
        ]

        path = QHBoxLayout()
        ex_box = _NodeDetailBlock("Извлечение", ex_level, ex_lines)
        ar1 = QLabel("→")
        ar1.setStyleSheet("font-size: 18px; color: gray;")
        va_box = _NodeDetailBlock("Валидация", va_level, va_lines)
        ar2 = QLabel("→")
        ar2.setStyleSheet("font-size: 18px; color: gray;")
        asm_box = _NodeDetailBlock("Сборка", asm_level, asm_lines)
        path.addWidget(ex_box, stretch=1)
        path.addWidget(ar1, alignment=Qt.AlignmentFlag.AlignVCenter)
        path.addWidget(va_box, stretch=1)
        path.addWidget(ar2, alignment=Qt.AlignmentFlag.AlignVCenter)
        path.addWidget(asm_box, stretch=1)
        inner.layout().addLayout(path)

    def apply_edits(self):
        tr = self.edited.draft.triples[self.triple_index]
        for role, (edit, _, _, _) in self._role_rows.items():
            kind = tr.get_node(role).type
            new_node = _draft_node_from_n3_input(kind, edit.text(), tr.get_node(role).source)
            self.edited.set_node(self.triple_index, role, new_node)

    def refresh(self):
        tr = self.edited.draft.triples[self.triple_index]
        idx = self.triple_index
        excluded = idx in self.edited.excluded
        s_n = _effective_node(self.edited, idx, "subject")
        p_n = _effective_node(self.edited, idx, "predicate")
        o_n = _effective_node(self.edited, idx, "object")

        if excluded:
            stripe_color = UI_COLOR_GRAY
        else:
            badge_level = _triple_badge_warn_level_nodes(s_n, p_n, o_n)
            stripe_color = _warn_color(badge_level)

        self._stripe.setStyleSheet(f"background-color: {stripe_color}; border-radius: 2px;")

        s = _term_n3_short(self.nm_graph, s_n.get_rdf_node())
        p = _term_n3_short(self.nm_graph, p_n.get_rdf_node())
        o = _term_n3_short(self.nm_graph, o_n.get_rdf_node())
        typ = tr.triple_type.name
        prefix = "[исключён] " if excluded else ""
        self._summary.setText(f"{prefix}#{idx} {typ}  |  {s}  {p}  {o}")

        self._exclude_btn.setText("Вернуть в модель" if excluded else "Исключить из модели")

        for role, (_, stripe, _, inner) in self._role_rows.items():
            node = _effective_node(self.edited, self.triple_index, role)
            lvl = _node_row_warn_level(node)
            stripe.setStyleSheet(f"background-color: {_warn_color(lvl)}; border-radius: 2px;")
            if inner.layout() and inner.layout().count():
                self._fill_details(role, inner)


class DocumentViewGraphTab(QWidget):
    """Черновой RDF-граф: просмотр, правки (EditedGraph) и дополнительные факты (Turtle)."""

    _SUPPLEMENTARY_DEFAULT = (
        '@prefix : <http://doc2onto.org/ontology#> .\n'
        "# Ниже можно дописать дополнительные факты на Turtle; они сохраняются отдельно от чернового графа.\n"
    )

    def __init__(self):
        super().__init__()
        self._document: Optional[Document] = None
        self._edited: Optional[EditedGraph] = None
        self._nm_graph = _make_prefix_graph()
        self._extraction: Optional[ExtractionResult] = None
        self._validation: Optional[ValidationResult] = None
        self._triple_widgets: List[_TripleRowWidget] = []

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_host)

        self._supp_label = QLabel("Дополнительные факты (Turtle)")
        self._supp = QTextEdit()
        self._supp.setFont(QFont("Consolas"))
        self._supp.setPlaceholderText(self._SUPPLEMENTARY_DEFAULT)
        self._supp.setMinimumHeight(120)

        self._save_btn = QPushButton("Сохранить правки и доп. факты")
        self._save_btn.clicked.connect(self._on_save)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.addWidget(self._supp_label)
        bl.addWidget(self._supp)
        bl.addWidget(self._save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._scroll)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def _clear_triples(self):
        for w in self._triple_widgets:
            w.deleteLater()
        self._triple_widgets.clear()
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_triple_changed(self):
        for w in self._triple_widgets:
            w.refresh()

    def _rebuild_triples(self):
        self._clear_triples()
        if self._edited is None:
            return
        for i in range(len(self._edited.draft.triples)):
            row = _TripleRowWidget(
                i,
                self._edited,
                self._nm_graph,
                self._extraction,
                self._validation,
                self._on_triple_changed,
            )
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._list_layout.addWidget(row)
            self._triple_widgets.append(row)

    def _on_save(self):
        if self._document is None or self._edited is None:
            return
        try:
            for w in self._triple_widgets:
                if w._expanded:
                    w.apply_edits()
            self._edited.save(self._document.draft_graph_edits_file_path())
            self._document.supplementary_facts_ttl_path().write_text(
                self._supp.toPlainText(), encoding="utf-8"
            )
            QMessageBox.information(self, "Сохранено", "Правки графа и дополнительные факты записаны на диск.")
        except OSError as ex:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить: {ex}")

    def set_document(self, document: Optional[Document]) -> bool:
        self._document = document
        self._edited = None
        self._extraction = None
        self._validation = None
        self._clear_triples()
        self._supp.clear()

        if document is None:
            return False

        path = document.draft_graph_file_path()
        if not path.exists():
            self._supp.setPlainText("")
            self._supp.setPlaceholderText("Черновой граф ещё не построен (запустите пайплайн до этапа сборки триплетов).")
            return False

        try:
            draft = DraftGraph.load(path)
        except Exception:
            self._supp.setPlaceholderText("Не удалось прочитать draft_graph.json")
            return False

        edits_path = document.draft_graph_edits_file_path()
        try:
            if edits_path.exists():
                self._edited = EditedGraph.load(edits_path, draft)
            else:
                self._edited = EditedGraph(draft)
        except Exception:
            self._edited = EditedGraph(draft)

        try:
            self._extraction = ExtractionResult.load(document.extraction_result_file_path())
        except Exception:
            self._extraction = None

        try:
            self._validation = ValidationResult.load(document.validation_result_file_path())
        except Exception:
            self._validation = None

        supp_path = document.supplementary_facts_ttl_path()
        text = read_text_file(supp_path)
        if text.strip():
            self._supp.setPlainText(text)
        else:
            self._supp.setPlainText(self._SUPPLEMENTARY_DEFAULT)

        self._rebuild_triples()
        return True
