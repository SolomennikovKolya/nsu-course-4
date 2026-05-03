from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urldefrag

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from ui.documents.view.common import read_text_file


def _warn_color(level: int) -> str:
    if level <= 0:
        return UI_COLOR_GREEN
    if level == 1:
        return UI_COLOR_YELLOW
    return UI_COLOR_RED


def _triple_type_badge_text(tt: DraftTriple.Type) -> str:
    m = {
        DraftTriple.Type.TYPE: "тип",
        DraftTriple.Type.OBJECT_PROPERTY: "объектное св-во",
        DraftTriple.Type.DATA_PROPERTY: "дата-свойство",
    }
    return f"({m[tt]})"


def _role_titles_for_triple_type(tt: DraftTriple.Type) -> Dict[str, str]:
    if tt == DraftTriple.Type.TYPE:
        return {
            "subject": "Экземпляр:",
            "predicate": "Тип:",
            "object": "Класс:",
        }
    if tt == DraftTriple.Type.OBJECT_PROPERTY:
        return {
            "subject": "Экземпляр:",
            "predicate": "Объектное св-во:",
            "object": "Экземпляр:",
        }
    if tt == DraftTriple.Type.DATA_PROPERTY:
        return {
            "subject": "Экземпляр:",
            "predicate": "Дата-свойство:",
            "object": "Литерал:",
        }


def _extraction_warn_level(
    field: Optional[str], extraction: Optional[ExtractionResult]
) -> int:
    if not field:
        return 0
    if extraction is None:
        return 1
    data = extraction.get_field(field)
    if not data:
        return 2
    return extraction.get_situation(field).warn_level()


def _validation_warn_level(
    field: Optional[str], validation: Optional[ValidationResult]
) -> int:
    if not field:
        return 0
    if validation is None:
        return 1
    vdata = validation.get_field(field)
    if not vdata:
        return 2
    return validation.get_situation(field).warn_level()


def _assembly_stage_warn_level(node: DraftNode) -> int:
    if node.error is not None:
        return 2
    if node.is_complete():
        return 0
    if node.source is None:
        return 0
    return 2


def _node_stripe_warn_level(
    edited: EditedGraph,
    triple_index: int,
    role: str,
    extraction: Optional[ExtractionResult],
    validation: Optional[ValidationResult],
) -> int:
    node = _effective_node(edited, triple_index, role)
    original = edited.draft.triples[triple_index].get_node(role)

    if not node.is_complete():
        return 2
    if not node.equals(original):
        return 0

    field = node.source
    return max(
        _extraction_warn_level(field, extraction),
        _validation_warn_level(field, validation),
        _assembly_stage_warn_level(node),
    )


def _triple_badge_warn_level(
    edited: EditedGraph,
    triple_index: int,
    extraction: Optional[ExtractionResult],
    validation: Optional[ValidationResult],
) -> int:
    return max(
        _node_stripe_warn_level(edited, triple_index, r, extraction, validation)
        for r in ("subject", "predicate", "object")
    )


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

        if isinstance(parsed, URIRef):
            u = str(parsed)
            if u.endswith("#"):
                frag = urldefrag(u).fragment
                if frag == "":
                    return DraftNode(
                        kind,
                        None,
                        "IRI задаёт только пространство имён (# без локального имени сущности)",
                        source,
                    )

        return DraftNode(kind, parsed, None, source)
    except Exception as ex:
        return DraftNode(kind, None, str(ex), source)


def _effective_node(edited: EditedGraph, triple_index: int, role: str) -> DraftNode:
    tr = edited.draft.triples[triple_index]
    return edited.node_overrides.get((triple_index, role), tr.get_node(role))


def _html_escape(s: object) -> str:
    t = "" if s is None else str(s)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap_detail_html(inner: str) -> str:
    return (
        '<div style="margin:0;padding:6px 10px 10px 14px;'
        "word-wrap:break-word;overflow-wrap:anywhere;word-break:break-word"
        f'">{inner}</div>'
    )


def _extraction_body_warn(
    field: Optional[str], extraction: Optional[ExtractionResult]
) -> Tuple[str, int]:
    if not field:
        return _wrap_detail_html(_html_escape("Нет привязки к полю")), 0
    if extraction is None:
        return _wrap_detail_html(_html_escape("Нет данных извлечения")), 1
    data = extraction.get_field(field)
    if not data:
        return _wrap_detail_html(_html_escape("Поле не найдено в результате извлечения")), 2
    sit = extraction.get_situation(field)
    inner = (
        "<b>Шаблон</b>:<br/>"
        f"• статус: {_html_escape('извлечено' if data.get('extracted_temp') else 'не извлечено')}<br/>"
        f"• значение: {_html_escape(data.get('value_temp') or '—')}<br/>"
        f"• ошибка: {_html_escape(data.get('error_temp') or '—')}"
    )
    if data.get("extracted_llm") is not None:
        inner += (
            "<br/><br/><b>LLM</b>:<br/>"
            f"• статус: {_html_escape('извлечено' if data.get('extracted_llm') else 'не извлечено')}<br/>"
            f"• значение: {_html_escape(data.get('value_llm') or '—')}<br/>"
            f"• ошибка: {_html_escape(data.get('error_llm') or '—')}"
        )
    return _wrap_detail_html(inner), sit.warn_level()


def _validation_body_warn(
    field: Optional[str], validation: Optional[ValidationResult]
) -> Tuple[str, int]:
    if not field:
        return _wrap_detail_html(_html_escape("Нет привязки к полю.")), 0
    if validation is None:
        return _wrap_detail_html(_html_escape("Нет данных валидации.")), 1
    vdata = validation.get_field(field)
    if not vdata:
        return _wrap_detail_html(_html_escape("Поле не найдено в результате валидации.")), 2
    vsit = validation.get_situation(field)
    inner = (
        "<b>Шаблон</b>:<br/>"
        f"• статус: {_html_escape('валидно' if vdata.get('valid_temp') else 'не валидно')}<br/>"
        f"• ошибка: {_html_escape(vdata.get('error_temp') or '—')}"
    )
    if vdata.get("valid_llm") is not None:
        inner += (
            "<br/><br/><b>LLM</b>:<br/>"
            f"• статус: {_html_escape('валидно' if vdata.get('valid_llm') else 'не валидно')}<br/>"
            f"• ошибка: {_html_escape(vdata.get('error_llm') or '—')}"
        )
    return _wrap_detail_html(inner), vsit.warn_level()


def _assembly_body_warn(node: DraftNode) -> Tuple[str, int]:
    inner = "<br/>".join(
        [
            f"Тип: {_html_escape(node.type.name)}",
            f"Значение: {_html_escape(node._to_json_dict().get('n3') or '—')}",
            f"Ошибка: {_html_escape(str(node.error) if node.error else '—')}",
            f"Источник: {_html_escape(node.source or '—')}",
        ]
    )
    return _wrap_detail_html(inner), _assembly_stage_warn_level(node)


class _AdaptiveDetailText(QTextEdit):
    """Read-only HTML: перенос по ширине виджета, высота = документ (без внутреннего скролла)."""

    def __init__(self, body_html: str):
        super().__init__()
        self.setReadOnly(True)
        self.setHtml(body_html)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(2)
        self.setStyleSheet("QTextEdit { background: transparent; }")
        self._fit_w = -1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        if w > 0 and w != self._fit_w:
            self._apply_height()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_height_deferred)

    def _apply_height_deferred(self):
        if self.viewport().width() < 1:
            return
        self._fit_w = -1
        self._apply_height()

    def _apply_height(self):
        w = self.viewport().width()
        if w < 1:
            return
        self._fit_w = w
        self.document().setTextWidth(w)
        h = int(self.document().size().height()) + 12
        self.setFixedHeight(max(24, h))


class _NodeDetailBlock(QGroupBox):
    """Один столбец «извлечение» / «валидация» / «сборка» (текст копируется)."""

    def __init__(self, title: str, warn_level: int, body_html: str):
        super().__init__(title)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; color: {_warn_color(warn_level)}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 0)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        te = _AdaptiveDetailText(body_html)
        lay.addWidget(te, alignment=Qt.AlignmentFlag.AlignTop)


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
        self._mute_edit_finished = False
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

        self._type_badge = QLabel(_triple_type_badge_text(self._triple_type))
        self._type_badge.setFont(mono)
        self._type_badge.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._type_badge.setStyleSheet("color: gray;")
        head.addWidget(self._type_badge)

        self._toggle = QPushButton("▼")
        self._toggle.setFixedWidth(28)
        self._toggle.clicked.connect(self._on_toggle)
        head.addWidget(self._toggle)

        outer.addLayout(head)

        self._body = QWidget()
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(0, 8, 0, 0)

        fm_role = QFontMetrics(mono)
        role_label_w = (
            max(
                fm_role.horizontalAdvance(lbl)
                for lbl in (
                    "Экземпляр:",
                    "Объектное св-во:",
                    "Тип:",
                    "Класс:",
                    "Дата-свойство:",
                    "Литерал:",
                )
            ) - 32
        )

        self._role_rows: Dict[str, Tuple[QLineEdit, QFrame, QPushButton, QWidget, QWidget]] = {}

        role_titles = _role_titles_for_triple_type(self._triple_type)
        for role in ("subject", "predicate", "object"):
            title = role_titles[role]
            role_fr = QFrame()
            role_fr.setFrameShape(QFrame.Shape.StyledPanel)
            rl = QVBoxLayout(role_fr)

            stripe = QFrame()
            stripe.setFixedWidth(4)

            cap_lbl = QLabel(title)
            cap_lbl.setFixedWidth(role_label_w)
            cap_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            edit = QLineEdit()
            edit.setFont(mono)

            arrow = QPushButton("▼")
            arrow.setFixedWidth(28)

            row_line = QHBoxLayout()
            row_line.addWidget(stripe)
            row_line.addWidget(cap_lbl)
            row_line.addWidget(edit, stretch=1)
            row_line.addWidget(arrow)

            details = QWidget()
            det_lay = QVBoxLayout(details)
            det_lay.setContentsMargins(8, 4, 8, 4)
            det_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
            details.setVisible(False)

            inner_details = QWidget()
            id_lay = QVBoxLayout(inner_details)
            id_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
            det_lay.addWidget(inner_details)

            def make_arrow_handler(r: str, inner_w: QWidget, btn: QPushButton, det: QWidget):
                def on_arrow_clicked():
                    will_show = not det.isVisible()
                    det.setVisible(will_show)
                    btn.setText("▲" if will_show else "▼")
                    if will_show:
                        self._fill_details(r, inner_w)

                return on_arrow_clicked

            arrow.clicked.connect(make_arrow_handler(role, inner_details, arrow, details))

            edit.editingFinished.connect(self._on_node_edit_finished)

            rl.addLayout(row_line)
            rl.addWidget(details)
            body_lay.addWidget(role_fr)

            self._role_rows[role] = (edit, stripe, arrow, details, inner_details)

        self._exclude_btn = QPushButton()
        self._exclude_btn.clicked.connect(self._on_toggle_exclude)
        body_lay.addWidget(self._exclude_btn)

        outer.addWidget(self._body)
        self._body.setVisible(False)

        self.refresh()

    def _collapse_all_role_details(self):
        for _role, (_edit, _stripe, arrow, details, _inner) in self._role_rows.items():
            details.setVisible(False)
            arrow.setText("▼")

    def _on_node_edit_finished(self):
        if not self._expanded or self._mute_edit_finished:
            return
        self.apply_edits()
        self.on_changed()

    def _on_toggle(self):
        had_expanded = self._expanded
        if had_expanded:
            self.apply_edits()
        self._mute_edit_finished = True
        try:
            self._expanded = not self._expanded
            self._body.setVisible(self._expanded)
            self._toggle.setText("▲" if self._expanded else "▼")
            if not self._expanded:
                self._collapse_all_role_details()
            else:
                self._populate_edits()
        finally:
            self._mute_edit_finished = False
        if had_expanded:
            self.on_changed()

    def _on_toggle_exclude(self):
        idx = self.triple_index
        if idx in self.edited.excluded:
            self.edited.include_triple(idx)
        else:
            self.edited.exclude_triple(idx)
        self.on_changed()

    def _populate_edits(self):
        for role, (edit, _, _, details, inner) in self._role_rows.items():
            node = _effective_node(self.edited, self.triple_index, role)
            n3 = node._to_json_dict().get("n3") or ""
            edit.setText(n3)
            if details.isVisible():
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

        tr = self.edited.draft.triples[self.triple_index]
        draft_node = tr.get_node(role)
        field = draft_node.source

        ex_body, ex_level = _extraction_body_warn(field, self.extraction)
        va_body, va_level = _validation_body_warn(field, self.validation)
        asm_body, asm_level = _assembly_body_warn(draft_node)

        path = QHBoxLayout()
        path.setAlignment(Qt.AlignmentFlag.AlignTop)
        ex_box = _NodeDetailBlock("Извлечение", ex_level, ex_body)
        ar1 = QLabel("→")
        ar1.setStyleSheet("font-size: 18px; color: gray;")
        va_box = _NodeDetailBlock("Валидация", va_level, va_body)
        ar2 = QLabel("→")
        ar2.setStyleSheet("font-size: 18px; color: gray;")
        asm_box = _NodeDetailBlock("Сборка", asm_level, asm_body)
        path.addWidget(ex_box, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        path.addWidget(ar1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        path.addWidget(va_box, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        path.addWidget(ar2, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        path.addWidget(asm_box, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        inner.layout().addLayout(path)

    def apply_edits(self):
        tr = self.edited.draft.triples[self.triple_index]
        for role, (edit, _, _, _, _) in self._role_rows.items():
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
            badge_level = _triple_badge_warn_level(
                self.edited, idx, self.extraction, self.validation
            )
            stripe_color = _warn_color(badge_level)

        self._stripe.setStyleSheet(f"background-color: {stripe_color}; border-radius: 2px;")

        s = _term_n3_short(self.nm_graph, s_n.get_rdf_node())
        p = _term_n3_short(self.nm_graph, p_n.get_rdf_node())
        o = _term_n3_short(self.nm_graph, o_n.get_rdf_node())
        self._summary.setText(f"{f'#{idx}':<3} {s} {p} {o}")

        self._exclude_btn.setText("Вернуть в модель" if excluded else "Исключить из модели")

        for role, (_, stripe, arrow, details, inner) in self._role_rows.items():
            lvl = _node_stripe_warn_level(
                self.edited,
                self.triple_index,
                role,
                self.extraction,
                self.validation,
            )
            stripe.setStyleSheet(f"background-color: {_warn_color(lvl)}; border-radius: 2px;")
            if details.isVisible() and inner.layout() and inner.layout().count():
                self._fill_details(role, inner)


class DocumentViewGraphTab(QWidget):
    """Черновой RDF-граф: просмотр, правки (EditedGraph) и дополнительные факты (Turtle)."""

    _SUPPLEMENTARY_DEFAULT = (
        '@prefix : <http://doc2onto.org/ontology#> .\n\n'
        "# Ниже можно дописать дополнительные факты на Turtle.\n"
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
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._triples_host = QWidget()
        self._triples_layout = QVBoxLayout(self._triples_host)
        self._triples_layout.setContentsMargins(0, 0, 0, 0)
        self._triples_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._list_layout.addWidget(self._triples_host)

        self._supp_label = QLabel("\nДополнительные факты:")
        self._supp = QTextEdit()
        self._supp.setFont(QFont("Consolas"))
        self._supp.setPlaceholderText(self._SUPPLEMENTARY_DEFAULT)
        self._supp.setMinimumHeight(72)
        self._supp.setMaximumHeight(160)
        self._supp.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )

        self._loading = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_graph)
        self._supp.textChanged.connect(self._on_supp_text_changed)

        self._list_layout.addWidget(self._supp_label)
        self._list_layout.addWidget(self._supp)

        self._scroll.setWidget(self._list_host)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll)

    def _clear_triples(self):
        for w in self._triple_widgets:
            w.deleteLater()
        self._triple_widgets.clear()
        while self._triples_layout.count():
            item = self._triples_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_triple_changed(self):
        for w in self._triple_widgets:
            w.refresh()
        self._persist_graph()

    def _on_supp_text_changed(self):
        self._persist_timer.stop()
        self._persist_timer.start(500)

    def _persist_graph(self):
        if self._loading or self._document is None or self._edited is None:
            return
        try:
            for w in self._triple_widgets:
                if w._expanded:
                    w.apply_edits()
            self._edited.save(self._document.draft_graph_edits_file_path())
            self._document.supplementary_facts_ttl_path().write_text(
                self._supp.toPlainText(), encoding="utf-8"
            )
        except OSError as ex:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить: {ex}")

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
            self._triples_layout.addWidget(row)
            self._triple_widgets.append(row)

    def set_document(self, document: Optional[Document]) -> bool:
        self._persist_timer.stop()
        self._loading = True
        try:
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
                self._supp.setPlaceholderText(
                    "Черновой граф ещё не построен (запустите пайплайн до этапа сборки триплетов)."
                )
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
                self._extraction = ExtractionResult.load(
                    document.extraction_result_file_path()
                )
            except Exception:
                self._extraction = None

            try:
                self._validation = ValidationResult.load(
                    document.validation_result_file_path()
                )
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
        finally:
            self._loading = False
