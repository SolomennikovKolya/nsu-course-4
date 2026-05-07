"""
Двухпанельный просмотр и редактирование чернового RDF-графа.

Левая панель — компактный список триплетов (без раскрывающихся карточек,
поэтому нет «скачков» компоновки при выборе). Правая панель — детальная
карточка выбранного триплета: редактирование узлов, история по pipeline
(Извлечение → Нормализация → Сборка), schema-подсказки по предикату,
список других триплетов, использующих ту же ноду.

Под списком триплетов — компактный редактор дополнительных Turtle-фактов
(supplementary_facts.ttl).

Если на этапе сборки графа было исключение, сверху рисуется баннер с
краткой ошибкой и кнопкой «Подробнее» — открывает QDialog с traceback и
контекстом из ``build_error.json``.
"""
from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urldefrag

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD
from rdflib.util import from_n3
from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.settings import ONTOLOGY_SCHEMA_PATH, SUBJECT_NAMESPACE_IRI
from core.graph.draft_graph import DraftGraph, DraftNode, DraftTriple, EditedGraph
from models.document import Document
from models.extraction_result import ExtractionResult
from ui.common.design import (
    UI_COLOR_DARK_GRAY,
    UI_COLOR_GRAY,
    UI_COLOR_GREEN,
    UI_COLOR_LINK_INDIVIDUAL,
    UI_COLOR_RED,
    UI_COLOR_TEXT_MUTED,
    UI_COLOR_TEXT_SECONDARY,
    UI_COLOR_TEXT_SUBTLE,
    UI_COLOR_YELLOW,
)
from ui.documents.view.common import read_text_file


# =====================================================================
# Утилитарные функции
# =====================================================================


def _warn_color(level: int) -> str:
    if level <= 0:
        return UI_COLOR_GREEN
    if level == 1:
        return UI_COLOR_YELLOW
    return UI_COLOR_RED


_TRIPLE_TYPE_LABELS: Dict[DraftTriple.Type, str] = {
    DraftTriple.Type.TYPE: "тип",
    DraftTriple.Type.OBJECT_PROPERTY: "объектное св-во",
    DraftTriple.Type.DATA_PROPERTY: "дата-свойство",
}


def _role_titles(tt: DraftTriple.Type) -> Dict[str, str]:
    if tt == DraftTriple.Type.TYPE:
        return {"subject": "Экземпляр", "predicate": "Тип", "object": "Класс"}
    if tt == DraftTriple.Type.OBJECT_PROPERTY:
        return {"subject": "Экземпляр", "predicate": "Объектное св-во", "object": "Экземпляр"}
    return {"subject": "Экземпляр", "predicate": "Дата-свойство", "object": "Литерал"}


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


def _draft_node_from_n3_input(
    kind: DraftNode.Type,
    n3_text: str,
    source: Optional[str],
    nsm=None,
) -> DraftNode:
    """Распарсить N3-форму узла. ``nsm`` нужен, чтобы корректно
    разрешать префиксованные IRI вроде ``:Персона_xxx`` и ``rdf:type``."""
    t = (n3_text or "").strip()
    if not t or t == "—":
        return DraftNode(kind, None, None, source)
    try:
        parsed = from_n3(t, nsm=nsm) if nsm is not None else from_n3(t)
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
                        kind, None,
                        "IRI задаёт только пространство имён (# без локального имени)",
                        source,
                    )
        return DraftNode(kind, parsed, None, source)
    except Exception as ex:  # noqa: BLE001
        return DraftNode(kind, None, str(ex), source)


def _effective_node(edited: EditedGraph, triple_index: int, role: str) -> DraftNode:
    tr = edited.draft.triples[triple_index]
    return edited.node_overrides.get((triple_index, role), tr.get_node(role))


def _html_escape(s: object) -> str:
    t = "" if s is None else str(s)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- warn-уровни ----------------------------------------------------------


def _extraction_warn_level(field: Optional[str], extr: Optional[ExtractionResult]) -> int:
    if not field:
        return 0
    if extr is None:
        return 1
    data = extr.get_field(field)
    if not data:
        return 2
    return extr.get_situation(field).warn_level()


def _normalization_warn_level(field: Optional[str], extr: Optional[ExtractionResult]) -> int:
    if not field:
        return 0
    if extr is None:
        return 1
    data = extr.get_field(field)
    if not data:
        return 2
    if extr.is_normalized(field):
        return 0
    return 2


def _assembly_stage_warn_level(node: DraftNode) -> int:
    if node.error is not None:
        return 2
    if node.is_complete():
        return 0
    if node.source is None:
        return 0
    return 2


def _node_warn_level(
    edited: EditedGraph,
    triple_index: int,
    role: str,
    extr: Optional[ExtractionResult],
) -> int:
    node = _effective_node(edited, triple_index, role)
    original = edited.draft.triples[triple_index].get_node(role)
    if not node.is_complete():
        return 2
    if not node.equals(original):
        return 0
    field = node.source
    return max(
        _extraction_warn_level(field, extr),
        _normalization_warn_level(field, extr),
        _assembly_stage_warn_level(node),
    )


def _triple_warn_level(
    edited: EditedGraph, triple_index: int, extr: Optional[ExtractionResult]
) -> int:
    return max(
        _node_warn_level(edited, triple_index, r, extr)
        for r in ("subject", "predicate", "object")
    )


def _can_generate_for_role(role: str, triple_type: DraftTriple.Type) -> bool:
    """Имеет ли смысл «сгенерировать значение через концепт» для данного
    узла. Концепты онтологии умеют считать IRI индивидов с хешем и
    типизированные литералы; для предикатов (свойств) и классов
    (object-роль в TYPE-триплете) такой генерации нет — они выбираются
    руками из онтологии.
    """
    if role == "predicate":
        return False
    if role == "object" and triple_type == DraftTriple.Type.TYPE:
        return False
    return True


# =====================================================================
# Schema cache: domain/range для предикатов
# =====================================================================


class _SchemaHints:
    """Лёгкий кеш domain/range для предикатов из schema.ttl.

    Подсказки используются в правой панели: при выборе триплета
    показываем, какой класс ожидается у subject и какой класс/тип — у
    object для текущего предиката.
    """

    def __init__(self):
        self._g: Optional[Graph] = None

    def _ensure_loaded(self) -> Optional[Graph]:
        if self._g is not None:
            return self._g
        if not ONTOLOGY_SCHEMA_PATH.exists():
            return None
        try:
            g = Graph()
            g.parse(ONTOLOGY_SCHEMA_PATH, format="turtle")
            self._g = g
            return g
        except Exception:  # noqa: BLE001
            return None

    def hints_for_predicate(self, predicate_iri: URIRef) -> Tuple[Optional[str], Optional[str]]:
        """Вернуть (domain, range) как короткие N3-имена. None — если не задано."""
        g = self._ensure_loaded()
        if g is None:
            return None, None
        domain = next(g.objects(predicate_iri, RDFS.domain), None)
        range_ = next(g.objects(predicate_iri, RDFS.range), None)
        nm = _make_prefix_graph().namespace_manager
        d = domain.n3(nm) if isinstance(domain, URIRef) else None
        r = range_.n3(nm) if isinstance(range_, URIRef) else None
        return d, r


# =====================================================================
# Build error: модель + диалог
# =====================================================================


class _BuildErrorReport:
    """Содержимое build_error.json."""

    def __init__(self, data: Dict):
        self.template_name: Optional[str] = (data.get("template") or {}).get("name")
        exc = data.get("exception") or {}
        self.exception_type: str = exc.get("type", "?")
        self.exception_message: str = exc.get("message", "")
        self.traceback: List[str] = list(exc.get("traceback") or [])
        self.context: Dict = data.get("context") or {}
        self.timestamp: Optional[str] = data.get("timestamp")

    @classmethod
    def load(cls, document: Document) -> Optional["_BuildErrorReport"]:
        path = document.build_error_file_path()
        if not path.exists():
            return None
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return None


class _BuildErrorDialog(QDialog):
    """Подробный отчёт об ошибке стадии сборки."""

    def __init__(self, report: _BuildErrorReport, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Ошибка построения графа")
        self.resize(720, 520)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b>{_html_escape(report.exception_type)}</b>: "
            f"{_html_escape(report.exception_message)}"
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            f"background:{UI_COLOR_RED}; color:white; padding:8px; border-radius:4px;"
        )
        layout.addWidget(header)

        if report.timestamp:
            layout.addWidget(QLabel(f"Время: {_html_escape(report.timestamp)}"))
        if report.template_name:
            layout.addWidget(QLabel(f"Шаблон: {_html_escape(report.template_name)}"))

        # Контекст.
        ctx_lines = []
        for key, val in (report.context or {}).items():
            if isinstance(val, list):
                val_repr = ", ".join(map(str, val)) if val else "—"
            else:
                val_repr = str(val)
            ctx_lines.append(f"<b>{_html_escape(key)}</b>: {_html_escape(val_repr)}")
        if ctx_lines:
            ctx_box = QLabel("<br/>".join(ctx_lines))
            ctx_box.setWordWrap(True)
            ctx_box.setStyleSheet(
                "padding:6px; background:rgba(255,255,255,0.06); "
                "border:1px solid rgba(255,255,255,0.10); border-radius:3px;"
            )
            layout.addWidget(ctx_box)

        layout.addWidget(QLabel("Traceback:"))
        tb_view = QTextEdit()
        tb_view.setReadOnly(True)
        tb_view.setFont(QFont("Consolas"))
        tb_view.setPlainText("\n".join(report.traceback))
        layout.addWidget(tb_view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# =====================================================================
# Помощник генерации значения узла через концепты
# =====================================================================


class _NodeGeneratorDialog(QDialog):
    """Помощник: построить IRI индивида или типизированный литерал через
    выбранный концепт онтологии.

    Какие концепты показывать определяется типом узла:
        * для IRI — все ``CLASS_INDIVIDUAL``-концепты (Persona, Group,
          Direction, Profile, Organization, Thesis, перечисления).
        * для LITERAL — ``DATATYPE``-концепты (Date, Email, Telephone).

    Live-предпросмотр считает результат прямо при вводе значения, OK
    активна только если предпросмотр валидный.
    """

    def __init__(self, kind: DraftNode.Type, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Сгенерировать значение узла")
        self.resize(580, 420)
        self.result_n3: str = ""
        self._kind = kind
        self._n3: str = ""
        self._concepts = self._collect_concepts(kind)

        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # --- Шапка-объяснение ---
        kind_text = "IRI индивида" if kind == DraftNode.Type.IRI else "типизированный литерал"
        header = QLabel(
            f"<b>Помощник:</b> построить {kind_text} с помощью концепта онтологии. "
            f"Концепт сам нормализует значение и посчитает каноническую форму "
            f"(хеш в IRI, ISO-дату, ссылку на индивид перечисления и т. п.)."
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            "padding:8px 10px; "
            "background:rgba(80,140,220,0.12); "
            "border-left:3px solid #5a8bd6; "
            "border-radius:2px; "
            f"color:{UI_COLOR_TEXT_SECONDARY};"
        )
        layout.addWidget(header)

        # --- Сгруппированные поля формы ---
        form = QFrame()
        # form.setStyleSheet(
        #     "QFrame { "
        #     "background:rgba(255,255,255,0.04); "
        #     "border:1px solid rgba(255,255,255,0.08); "
        #     "border-radius:4px; "
        #     "}"
        # )
        form_lay = QVBoxLayout(form)
        form_lay.setContentsMargins(12, 10, 12, 12)
        form_lay.setSpacing(6)

        form_lay.addWidget(QLabel("<b>Концепт онтологии:</b>"))
        self._combo = QComboBox()
        for cls in self._concepts:
            label = cls.onto_class_local or cls.name
            self._combo.addItem(f"{label}  ({cls.name})", cls)
        form_lay.addWidget(self._combo)

        form_lay.addSpacing(4)
        form_lay.addWidget(QLabel("<b>Сырое значение:</b>"))
        self._input = QLineEdit()
        self._input.setFont(mono)
        self._input.setPlaceholderText("например: Иванов Иван Иванович")
        form_lay.addWidget(self._input)

        layout.addWidget(form)

        # --- Предпросмотр результата ---
        layout.addWidget(QLabel("<b>Предпросмотр результата:</b>"))
        self._preview = QLabel()
        self._preview.setFont(mono)
        self._preview.setWordWrap(True)
        self._preview.setMinimumHeight(64)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._preview.setStyleSheet(
            "padding:10px 12px; "
            "background:rgba(255,255,255,0.06); "
            "border:1px solid rgba(255,255,255,0.10); "
            "border-radius:3px; "
            f"color:{UI_COLOR_TEXT_SECONDARY};"
        )
        layout.addWidget(self._preview)
        layout.addStretch(1)

        # --- Кнопки ---
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Подставить")
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._input.textChanged.connect(self._update_preview)
        self._combo.currentIndexChanged.connect(self._update_preview)

        if not self._concepts:
            self._preview.setText(
                f"<span style='color:{UI_COLOR_RED};'>"
                f"Нет подходящих концептов для этого типа узла."
                f"</span>"
            )
            self._input.setEnabled(False)
            self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self._update_preview()

    @staticmethod
    def _collect_concepts(kind: DraftNode.Type):
        """Все доступные концепты, отфильтрованные по типу узла."""
        # Локальный импорт: запросто может тяжёлый pymorphy3 (PersonConcept) —
        # подгружаем лениво, только при открытии диалога.
        from core.concepts.base import ConceptKind
        from core.concepts.date import DateConcept
        from core.concepts.degree import DegreeConcept
        from core.concepts.direction import DirectionConcept
        from core.concepts.email import EmailConcept
        from core.concepts.grade import GradeConcept
        from core.concepts.group import GroupConcept
        from core.concepts.organization import OrganizationConcept
        from core.concepts.person import PersonConcept
        from core.concepts.position import PositionConcept
        from core.concepts.practice_kind import PracticeKindConcept
        from core.concepts.profile import ProfileConcept
        from core.concepts.telephone import TelephoneConcept
        from core.concepts.thesis import ThesisConcept
        from core.concepts.title import TitleConcept

        all_concepts = [
            PersonConcept, OrganizationConcept, GroupConcept, DirectionConcept,
            ProfileConcept, ThesisConcept, PositionConcept, DegreeConcept,
            TitleConcept, PracticeKindConcept, GradeConcept,
            DateConcept, EmailConcept, TelephoneConcept,
        ]
        target_kind = (
            ConceptKind.CLASS_INDIVIDUAL
            if kind == DraftNode.Type.IRI
            else ConceptKind.DATATYPE
        )
        return [c for c in all_concepts if c.kind == target_kind]

    def _current_concept(self):
        idx = self._combo.currentIndex()
        if 0 <= idx < len(self._concepts):
            return self._concepts[idx]
        return None

    def _update_preview(self):
        from core.concepts.base import ConceptError, ConceptKind
        from core.concepts.date import DateConcept

        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        cls = self._current_concept()
        raw = self._input.text()
        self._n3 = ""

        if cls is None or not raw.strip():
            self._preview.setText("(введите значение)")
            ok_btn.setEnabled(False)
            return

        try:
            parts = cls.parse(raw)
        except ConceptError as ex:
            self._preview.setText(
                f"<span style='color:{UI_COLOR_RED};'>Ошибка: {_html_escape(str(ex))}</span>"
            )
            ok_btn.setEnabled(False)
            return
        except Exception as ex:  # noqa: BLE001
            self._preview.setText(
                f"<span style='color:{UI_COLOR_RED};'>Непредвиденная ошибка: {_html_escape(str(ex))}</span>"
            )
            ok_btn.setEnabled(False)
            return

        nm = _make_prefix_graph().namespace_manager
        if cls.kind == ConceptKind.CLASS_INDIVIDUAL:
            try:
                local = cls.iri_local(parts)
            except Exception as ex:  # noqa: BLE001
                self._preview.setText(
                    f"<span style='color:{UI_COLOR_RED};'>Ошибка построения IRI: {_html_escape(str(ex))}</span>"
                )
                ok_btn.setEnabled(False)
                return
            iri = URIRef(SUBJECT_NAMESPACE_IRI + local)
            n3 = iri.n3(nm)
            self._preview.setText(f"<b>IRI индивида:</b> <code>{_html_escape(n3)}</code>")
        else:
            datatype = XSD.date if cls is DateConcept else XSD.string
            lit = Literal(parts.canonical, datatype=datatype)
            n3 = lit.n3(nm)
            self._preview.setText(f"<b>Литерал:</b> <code>{_html_escape(n3)}</code>")

        self._n3 = n3
        ok_btn.setEnabled(True)

    def _on_accept(self):
        if not self._n3:
            self.reject()
            return
        self.result_n3 = self._n3
        self.accept()


# =====================================================================
# Левая панель: компактная строка триплета
# =====================================================================


class _TripleListItem(QFrame):
    """Одна строка списка триплетов — без раскрытия. Только цветной стрипп
    и краткое N3-резюме.

    Высота подстраивается под длину текста (с word-wrap), но не меньше
    двух строк — см. :meth:`compute_height_for_width`. Главный виджет
    пересчитывает sizeHint каждой строки при изменении ширины списка.
    """

    # Минимум — две строки текста + вертикальные отступы.
    _MIN_TEXT_LINES = 2

    def __init__(self, triple_index: int, edited: EditedGraph, nm_graph: Graph):
        super().__init__()
        self.triple_index = triple_index
        self.edited = edited
        self.nm_graph = nm_graph

        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Минимум — высота 2 строк, максимум растёт по контенту.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        self._stripe = QFrame()
        self._stripe.setFixedWidth(4)
        outer.addWidget(self._stripe)

        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")

        self._index_lbl = QLabel(f"#{triple_index}")
        self._index_lbl.setFont(mono)
        self._index_lbl.setStyleSheet("color:gray;")
        self._index_lbl.setFixedWidth(40)
        outer.addWidget(self._index_lbl)

        self._summary = QLabel()
        self._summary.setFont(mono)
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        outer.addWidget(self._summary, stretch=1)

        # self._type_badge = QLabel()
        # self._type_badge.setFont(mono)
        # self._type_badge.setStyleSheet("color:gray;")
        # self._type_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # outer.addWidget(self._type_badge)

        self.refresh(extraction=None)

    def refresh(self, extraction: Optional[ExtractionResult]):
        idx = self.triple_index
        tr = self.edited.draft.triples[idx]
        excluded = idx in self.edited.excluded

        s = _effective_node(self.edited, idx, "subject")
        p = _effective_node(self.edited, idx, "predicate")
        o = _effective_node(self.edited, idx, "object")

        s_n3 = _term_n3_short(self.nm_graph, s.get_rdf_node())
        p_n3 = _term_n3_short(self.nm_graph, p.get_rdf_node())
        o_n3 = _term_n3_short(self.nm_graph, o.get_rdf_node())
        self._summary.setText(f"{s_n3}  {p_n3}  {o_n3}")

        # self._type_badge.setText(f"({_TRIPLE_TYPE_LABELS[tr.triple_type]})")

        if excluded:
            stripe_color = UI_COLOR_GRAY
            self.setStyleSheet(
                "QFrame { background: " + UI_COLOR_DARK_GRAY + "; color: " + UI_COLOR_TEXT_MUTED + "; }"
            )
        else:
            level = _triple_warn_level(self.edited, idx, extraction)
            stripe_color = _warn_color(level)
            self.setStyleSheet("")

        self._stripe.setStyleSheet(f"background-color: {stripe_color}; border-radius: 1px;")

    def compute_height_for_width(self, total_width: int) -> int:
        """Высота строки для заданной общей ширины (для setSizeHint).

        Учитывает: фиксированную ширину стрипа/индекса + spacing + margins;
        на оставшуюся ширину считает height-of-text у summary через
        word-wrap. Возвращает максимум(текст, MIN_TEXT_LINES * lineSpacing).
        """
        # Ширина «несжимаемых» элементов: стрипп (4) + индекс-лейбл (40) +
        # 2 отступа по 6px между виджетами + outer-margins (4+4) + запас.
        fixed_w = 4 + 40 + (6 * 2) + (4 + 4) + 8
        avail_w = max(80, total_width - fixed_w)

        fm = self._summary.fontMetrics()
        text = self._summary.text() or "X"
        # boundingRect c TextWordWrap даёт честную высоту для нескольких строк.
        rect = fm.boundingRect(0, 0, avail_w, 100000, int(Qt.TextFlag.TextWordWrap), text)
        h_text = rect.height()
        h_min = fm.lineSpacing() * self._MIN_TEXT_LINES
        h_content = max(h_text, h_min)

        # Вертикальные внешние отступы (4 + 4) + небольшой запас на штрихи.
        return h_content + 12


# =====================================================================
# Правая панель: детальная карточка триплета
# =====================================================================


class _TripleDetailPanel(QWidget):
    """Детальный вид и редактор выбранного триплета."""

    def __init__(
        self,
        nm_graph: Graph,
        schema_hints: _SchemaHints,
        on_changed: Callable[[], None],
    ):
        super().__init__()
        self._nm_graph = nm_graph
        self._schema = schema_hints
        self._on_changed = on_changed

        self._edited: Optional[EditedGraph] = None
        self._extraction: Optional[ExtractionResult] = None
        self._triple_index: Optional[int] = None
        self._mute_signals = False

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self._title = QLabel()
        self._title.setStyleSheet("font-weight:bold; font-size:13px;")
        outer.addWidget(self._title)

        # Три блока узлов (subject / predicate / object).
        self._node_blocks: Dict[str, _NodeEditorBlock] = {}
        for role in ("subject", "predicate", "object"):
            block = _NodeEditorBlock(
                role,
                self._nm_graph,
                on_edit_finished=self._on_role_edit_finished,
                on_reset=self._on_role_reset,
                on_generate=self._on_role_generate,
            )
            outer.addWidget(block)
            self._node_blocks[role] = block

        # Schema hints (под блоками). Полупрозрачный голубоватый overlay +
        # цветной border-left — читаемо и в тёмной, и в светлой теме.
        self._hints_lbl = QLabel()
        self._hints_lbl.setWordWrap(True)
        self._hints_lbl.setStyleSheet(
            "padding:6px 10px; "
            "background:rgba(80,140,220,0.12); "
            "border-left:3px solid #5a8bd6; "
            "border-radius:2px; "
            f"color:{UI_COLOR_TEXT_SECONDARY};"
        )
        outer.addWidget(self._hints_lbl)

        # Used-in (другие триплеты, где встречается выбранная нода).
        self._usedin_label = QLabel("Номера триплетов, в которых встречается:")
        self._usedin_label.setStyleSheet(
            f"color:{UI_COLOR_TEXT_MUTED}; font-style:italic;"
        )
        outer.addWidget(self._usedin_label)
        self._usedin_list = QLabel()
        self._usedin_list.setWordWrap(True)
        self._usedin_list.setStyleSheet(f"color:{UI_COLOR_TEXT_SECONDARY};")
        self._usedin_list.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self._usedin_list)

        outer.addStretch(1)

        # Кнопки действий.
        actions = QHBoxLayout()
        self._exclude_btn = QPushButton()
        self._exclude_btn.clicked.connect(self._on_toggle_exclude)
        actions.addWidget(self._exclude_btn)
        actions.addStretch(1)
        outer.addLayout(actions)

    # ---------- API ----------

    def set_data(
        self,
        edited: Optional[EditedGraph],
        extraction: Optional[ExtractionResult],
        triple_index: Optional[int],
    ):
        self._edited = edited
        self._extraction = extraction
        self._triple_index = triple_index
        self._refresh_all()

    def refresh(self):
        """Перерисовать содержимое (после внешнего изменения графа)."""
        self._refresh_all()

    # ---------- внутренние ----------

    def _refresh_all(self):
        self._mute_signals = True
        try:
            if self._edited is None or self._triple_index is None:
                self._set_empty()
                return

            tr = self._edited.draft.triples[self._triple_index]
            excluded = self._triple_index in self._edited.excluded
            overrides_set = {
                role for (ti, role) in self._edited.node_overrides
                if ti == self._triple_index
            }

            title_marks: List[str] = []
            if excluded:
                title_marks.append("ИСКЛЮЧЁН")
            if overrides_set:
                title_marks.append(
                    "ИЗМЕНЕН (" + ", ".join(sorted(overrides_set)) + ")"
                )
            title_text = (
                f"Триплет #{self._triple_index} ({_TRIPLE_TYPE_LABELS[tr.triple_type]})"
            )
            if title_marks:
                title_text += "  ·  " + "  ·  ".join(title_marks)
            self._title.setText(title_text)

            role_titles = _role_titles(tr.triple_type)
            for role, block in self._node_blocks.items():
                node = _effective_node(self._edited, self._triple_index, role)
                level = _node_warn_level(self._edited, self._triple_index, role, self._extraction)
                used_in = self._find_used_in(node, exclude_index=self._triple_index)
                block.set_state(
                    role_label=role_titles[role],
                    node=node,
                    warn_level=level,
                    extraction=self._extraction,
                    used_in_count=len(used_in),
                    is_overridden=(role in overrides_set),
                    can_generate=_can_generate_for_role(role, tr.triple_type),
                )

            self._refresh_hints(tr)
            self._refresh_usedin()
            self._exclude_btn.setText("Вернуть в модель" if excluded else "Исключить из модели")
            self._exclude_btn.setEnabled(True)
        finally:
            self._mute_signals = False

    def _set_empty(self):
        self._title.setText("Выберите триплет в списке слева")
        for block in self._node_blocks.values():
            block.set_empty()
        self._hints_lbl.setText("")
        self._hints_lbl.setVisible(False)
        self._usedin_label.setVisible(False)
        self._usedin_list.setText("")
        self._exclude_btn.setText("—")
        self._exclude_btn.setEnabled(False)

    def _refresh_hints(self, tr: DraftTriple):
        if tr.triple_type == DraftTriple.Type.TYPE:
            self._hints_lbl.setText(
                "Подсказка: тип-триплет (rdf:type). subject — именованный индивид, "
                "object — класс из онтологии."
            )
            self._hints_lbl.setVisible(True)
            return

        pred_node = _effective_node(self._edited, self._triple_index, "predicate")
        pred_iri = pred_node.get_rdf_node()
        if not isinstance(pred_iri, URIRef):
            self._hints_lbl.setVisible(False)
            return
        domain, range_ = self._schema.hints_for_predicate(pred_iri)
        if domain is None and range_ is None:
            self._hints_lbl.setText(
                f"Schema-подсказка: для предиката {pred_iri.n3(self._nm_graph.namespace_manager)} "
                f"не задано rdfs:domain/range в schema.ttl."
            )
        else:
            parts = []
            if domain:
                parts.append(f"<b>Ожидаемый класс subject:</b> {_html_escape(domain)}")
            if range_:
                parts.append(f"<b>Ожидаемый range object:</b> {_html_escape(range_)}")
            self._hints_lbl.setText("Schema-подсказка — " + "; ".join(parts))
        self._hints_lbl.setVisible(True)

    def _refresh_usedin(self):
        # Соберём used_in для каждого узла и покажем кратко.
        if self._edited is None or self._triple_index is None:
            self._usedin_label.setVisible(False)
            self._usedin_list.setText("")
            return

        sections: List[str] = []
        for role in ("subject", "predicate", "object"):
            node = _effective_node(self._edited, self._triple_index, role)
            if not node.is_complete():
                continue
            used = self._find_used_in(node, exclude_index=self._triple_index)
            if not used:
                continue
            head = f"<b>{role}</b>: " + ", ".join(f"{i}" for i in used)
            sections.append(head)

        if not sections:
            self._usedin_label.setVisible(False)
            self._usedin_list.setText("")
        else:
            self._usedin_label.setVisible(True)
            self._usedin_list.setText("<br/>".join(sections))

    def _find_used_in(self, node: DraftNode, exclude_index: int) -> List[int]:
        """Индексы триплетов, где встречается тот же rdflib-узел."""
        if self._edited is None or not node.is_complete():
            return []
        rdf = node.get_rdf_node()
        result: List[int] = []
        for i, tr in enumerate(self._edited.draft.triples):
            if i == exclude_index:
                continue
            for r in ("subject", "predicate", "object"):
                eff = _effective_node(self._edited, i, r)
                if eff.is_complete() and eff.get_rdf_node() == rdf:
                    result.append(i)
                    break
        return result

    def _on_role_edit_finished(self, role: str, n3_text: str):
        if self._mute_signals or self._edited is None or self._triple_index is None:
            return
        tr = self._edited.draft.triples[self._triple_index]
        kind = tr.get_node(role).type
        source = tr.get_node(role).source
        # Передаём nsm, иначе ":Персона_xxx" / "rdf:type" не разрешаются
        # до полного IRI и узел получается невалидным.
        new_node = _draft_node_from_n3_input(
            kind, n3_text, source, nsm=self._nm_graph.namespace_manager
        )
        self._edited.set_node(self._triple_index, role, new_node)
        self._on_changed()

    def _on_role_reset(self, role: str):
        """Сбросить ручную правку у узла: записать оригинальный узел —
        :meth:`EditedGraph.set_node` сам убирает override, когда узел
        совпадает с исходным."""
        if self._edited is None or self._triple_index is None:
            return
        original = self._edited.draft.triples[self._triple_index].get_node(role)
        # Копия, чтобы не разделять идентичность с исходным узлом графа.
        self._edited.set_node(self._triple_index, role, original.copy())
        self._on_changed()

    def _on_role_generate(self, role: str):
        """Открыть :class:`_NodeGeneratorDialog` и подставить результат
        в N3-поле узла, как если бы пользователь сам ввёл и нажал Enter."""
        if self._edited is None or self._triple_index is None:
            return
        tr = self._edited.draft.triples[self._triple_index]
        kind = tr.get_node(role).type
        dialog = _NodeGeneratorDialog(kind, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        n3_text = dialog.result_n3
        if not n3_text:
            return
        # Подставляем визуально и применяем как обычное редактирование.
        block = self._node_blocks[role]
        block.set_n3(n3_text)
        self._on_role_edit_finished(role, n3_text)

    def _on_toggle_exclude(self):
        if self._edited is None or self._triple_index is None:
            return
        idx = self._triple_index
        if idx in self._edited.excluded:
            self._edited.include_triple(idx)
        else:
            self._edited.exclude_triple(idx)
        self._on_changed()


# =====================================================================
# Один редактируемый узел (subject / predicate / object)
# =====================================================================


class _NodeEditorBlock(QFrame):
    """Узел триплета: цветной стрипп, label, N3-редактор, источник, pipeline."""

    def __init__(
        self,
        role: str,
        nm_graph: Graph,
        on_edit_finished: Callable[[str, str], None],
        on_reset: Callable[[str], None],
        on_generate: Callable[[str], None],
    ):
        super().__init__()
        self._role = role
        self._nm_graph = nm_graph
        self._on_edit_finished = on_edit_finished
        self._on_reset = on_reset
        self._on_generate = on_generate

        self.setFrameShape(QFrame.Shape.StyledPanel)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        self._stripe = QFrame()
        self._stripe.setFixedWidth(4)
        outer.addWidget(self._stripe)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(2)
        outer.addLayout(right, stretch=1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._role_lbl = QLabel()
        self._role_lbl.setStyleSheet("font-weight:bold;")
        head.addWidget(self._role_lbl)

        # Бейдж «ИЗМЕНЕН» — виден, когда у узла есть override.
        self._override_badge = QLabel("ИЗМЕНЕН")
        self._override_badge.setStyleSheet(
            f"color:{UI_COLOR_LINK_INDIVIDUAL}; font-weight:bold; font-size:10px;"
        )
        self._override_badge.setVisible(False)
        head.addWidget(self._override_badge)

        head.addStretch(1)
        self._used_in_lbl = QLabel()
        self._used_in_lbl.setStyleSheet(
            f"color:{UI_COLOR_TEXT_MUTED}; font-style:italic;"
        )
        head.addWidget(self._used_in_lbl)
        right.addLayout(head)

        # Поле ввода + 2 маленькие кнопки в одной строке.
        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        edit_row.setSpacing(4)

        mono = QFont("Consolas")
        if not mono.exactMatch():
            mono = QFont("Courier New")
        self._edit = QLineEdit()
        self._edit.setFont(mono)
        self._edit.editingFinished.connect(self._emit_edit_finished)
        edit_row.addWidget(self._edit, stretch=1)

        # Кнопка сброса ручной правки.
        self._reset_btn = QPushButton("↺")
        self._reset_btn.setFixedWidth(28)
        self._reset_btn.setToolTip(
            "Сбросить ручную правку и вернуть исходное значение, "
            "посчитанное стадией сборки графа."
        )
        self._reset_btn.clicked.connect(self._emit_reset)
        self._reset_btn.setVisible(False)
        edit_row.addWidget(self._reset_btn)

        # Кнопка-помощник: открывает _NodeGeneratorDialog.
        # Видимость задаётся в set_state на основе типа триплета и роли:
        # она имеет смысл только для индивидов и литералов; для предикатов
        # (свойств) и классов (object роль в TYPE-триплете) — нет.
        self._gen_btn = QPushButton("⚙")
        self._gen_btn.setFixedWidth(28)
        self._gen_btn.setToolTip(
            "Сгенерировать значение через концепт онтологии "
            "(IRI индивида с хешем или типизированный литерал)."
        )
        self._gen_btn.clicked.connect(self._emit_generate)
        self._gen_btn.setVisible(False)
        edit_row.addWidget(self._gen_btn)

        right.addLayout(edit_row)

        self._meta_lbl = QLabel()
        self._meta_lbl.setWordWrap(True)
        self._meta_lbl.setStyleSheet(f"color:{UI_COLOR_TEXT_MUTED};")
        right.addWidget(self._meta_lbl)

        # Pipeline: Извлечение → Нормализация → Сборка. Нейтральный
        # полупрозрачный overlay — корректно ложится на тёмный фон.
        self._pipeline_lbl = QLabel()
        self._pipeline_lbl.setWordWrap(True)
        self._pipeline_lbl.setStyleSheet(
            "padding:4px 8px; "
            "background:rgba(255,255,255,0.05); "
            "border:1px solid rgba(255,255,255,0.08); "
            "border-radius:3px; "
            f"color:{UI_COLOR_TEXT_SECONDARY}; "
            "font-size:11px;"
        )
        right.addWidget(self._pipeline_lbl)

    # ---------- API ----------

    def set_state(
        self,
        *,
        role_label: str,
        node: DraftNode,
        warn_level: int,
        extraction: Optional[ExtractionResult],
        used_in_count: int,
        is_overridden: bool,
        can_generate: bool,
    ):
        self.setEnabled(True)
        self._role_lbl.setText(f"{role_label}:")
        self._gen_btn.setVisible(can_generate)

        # Стрипп: красный важнее всего; иначе override → голубой; иначе обычный warn.
        if warn_level >= 2:
            stripe_color = _warn_color(warn_level)
        elif is_overridden:
            stripe_color = UI_COLOR_LINK_INDIVIDUAL
        else:
            stripe_color = _warn_color(warn_level)
        self._stripe.setStyleSheet(
            f"background-color:{stripe_color}; border-radius:1px;"
        )

        self._override_badge.setVisible(is_overridden)
        self._reset_btn.setVisible(is_overridden)

        n3 = node._to_json_dict().get("n3") or ""
        self._edit.blockSignals(True)
        self._edit.setText(n3)
        self._edit.blockSignals(False)

        # Метаданные узла.
        meta_parts = []
        if node.source:
            meta_parts.append(f"источник: {_html_escape(node.source)}")
        if node.error:
            meta_parts.append(
                f"<span style='color:{UI_COLOR_RED};'>ошибка: {_html_escape(node.error)}</span>"
            )
        if not node.is_complete() and node.error is None:
            meta_parts.append(
                f"<span style='color:{UI_COLOR_RED};'>значение отсутствует</span>"
            )
        self._meta_lbl.setText(" · ".join(meta_parts) if meta_parts else "")

        if used_in_count > 0:
            self._used_in_lbl.setText(f"используется ещё в {used_in_count} триплете(ах)")
            self._used_in_lbl.setVisible(True)
        else:
            self._used_in_lbl.setVisible(False)

        self._pipeline_lbl.setText(self._pipeline_html(node, extraction))

    def set_empty(self):
        self.setEnabled(False)
        self._role_lbl.setText("")
        self._stripe.setStyleSheet("background-color: transparent;")
        self._edit.blockSignals(True)
        self._edit.setText("")
        self._edit.blockSignals(False)
        self._meta_lbl.setText("")
        self._pipeline_lbl.setText("")
        self._used_in_lbl.setVisible(False)
        self._override_badge.setVisible(False)
        self._reset_btn.setVisible(False)
        self._gen_btn.setVisible(False)

    def set_n3(self, n3_text: str):
        """Программно подставить N3-значение в поле ввода (без сигналов)."""
        self._edit.blockSignals(True)
        self._edit.setText(n3_text)
        self._edit.blockSignals(False)

    # ---------- pipeline ----------

    def _pipeline_html(self, node: DraftNode, extr: Optional[ExtractionResult]) -> str:
        field = node.source
        ext_part = self._extraction_summary(field, extr)
        norm_part = self._normalization_summary(field, extr)
        asm_part = self._assembly_summary(node)
        return f"Извлечение: {ext_part} → Нормализация: {norm_part} → Сборка: {asm_part}"

    @staticmethod
    def _extraction_summary(field: Optional[str], extr: Optional[ExtractionResult]) -> str:
        if not field:
            return f"<span style='color:{UI_COLOR_TEXT_MUTED};'>нет поля</span>"
        if extr is None:
            return f"<span style='color:{UI_COLOR_YELLOW};'>нет данных</span>"
        data = extr.get_field(field)
        if not data:
            return f"<span style='color:{UI_COLOR_RED};'>не найдено</span>"
        sit = extr.get_situation(field).short_msg()
        value = extr.get_value_raw(field) or "—"
        return f"{_html_escape(sit)} «{_html_escape(value)[:60]}»"

    @staticmethod
    def _normalization_summary(field: Optional[str], extr: Optional[ExtractionResult]) -> str:
        if not field or extr is None:
            return f"<span style='color:{UI_COLOR_TEXT_MUTED};'>—</span>"
        data = extr.get_field(field)
        if not data:
            return f"<span style='color:{UI_COLOR_TEXT_MUTED};'>—</span>"
        normalized = data.get("normalized")
        if normalized is True:
            return f"OK «{_html_escape(data.get('value_normalized') or '—')[:60]}»"
        if normalized is False:
            return (
                f"<span style='color:{UI_COLOR_RED};'>отвергнуто: "
                f"{_html_escape(data.get('error_normalized') or '—')}</span>"
            )
        return f"<span style='color:{UI_COLOR_TEXT_MUTED};'>не запускалось</span>"

    @staticmethod
    def _assembly_summary(node: DraftNode) -> str:
        if node.error is not None:
            return f"<span style='color:{UI_COLOR_RED};'>{_html_escape(str(node.error))}</span>"
        if node.is_complete():
            return "OK"
        return f"<span style='color:{UI_COLOR_RED};'>значение отсутствует</span>"

    def _emit_edit_finished(self):
        self._on_edit_finished(self._role, self._edit.text())

    def _emit_reset(self):
        self._on_reset(self._role)

    def _emit_generate(self):
        self._on_generate(self._role)


# =====================================================================
# Главный виджет вкладки
# =====================================================================


class DocumentViewGraphTab(QWidget):
    """Двухпанельный просмотр чернового RDF-графа документа."""

    _SUPPLEMENTARY_DEFAULT = (
        "@prefix : <http://doc2onto.org/ontology#> .\n\n"
        "# Ниже можно дописать дополнительные факты на Turtle.\n"
    )

    def __init__(self):
        super().__init__()
        self._document: Optional[Document] = None
        self._edited: Optional[EditedGraph] = None
        self._nm_graph = _make_prefix_graph()
        self._extraction: Optional[ExtractionResult] = None
        self._schema = _SchemaHints()
        self._build_error: Optional[_BuildErrorReport] = None
        self._loading = False

        self._items: List[_TripleListItem] = []
        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Баннер ошибки сборки (скрыт, если ошибки нет).
        self._error_banner = self._build_error_banner()
        layout.addWidget(self._error_banner)
        self._error_banner.setVisible(False)

        # Splitter горизонтальный: список | детали.
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self._main_splitter, 1)

        # Левая часть — внутренний splitter (триплеты сверху, supplementary снизу).
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._main_splitter.addWidget(left_splitter)

        # Список триплетов.
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        # При изменении ширины viewport — пересчитать высоту каждой строки,
        # чтобы word-wrap влез без обрезки.
        self._list_widget.viewport().installEventFilter(self)
        left_splitter.addWidget(self._list_widget)

        # Supplementary turtle.
        supp_box = QWidget()
        supp_lay = QVBoxLayout(supp_box)
        supp_lay.setContentsMargins(4, 4, 4, 4)
        supp_lay.setSpacing(4)
        supp_lay.addWidget(QLabel("Дополнительные факты (Turtle):"))
        self._supp = QTextEdit()
        self._supp.setFont(QFont("Consolas"))
        self._supp.setPlaceholderText(self._SUPPLEMENTARY_DEFAULT)
        self._supp.textChanged.connect(self._on_supp_changed)
        supp_lay.addWidget(self._supp, 1)
        left_splitter.addWidget(supp_box)

        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 0)
        left_splitter.setSizes([500, 100])

        # Правая часть — стек: пусто / детальная карточка.
        self._detail_stack = QStackedWidget()
        self._main_splitter.addWidget(self._detail_stack)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([500, 500])

        empty = QLabel("Выберите триплет слева для просмотра и редактирования.")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("color:gray;")
        self._detail_stack.addWidget(empty)

        self._detail_panel = _TripleDetailPanel(
            self._nm_graph, self._schema, on_changed=self._on_detail_changed
        )
        # Оборачиваем в скролл — детали могут быть длинными.
        scroll = QScrollArea()
        scroll.setWidget(self._detail_panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._detail_stack.addWidget(scroll)

        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 2)

    def _build_error_banner(self) -> QWidget:
        banner = QFrame()
        banner.setStyleSheet(
            f"background:{UI_COLOR_RED}; color:white; padding:6px 10px;"
        )
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(8, 4, 8, 4)
        self._error_text = QLabel()
        self._error_text.setWordWrap(True)
        lay.addWidget(self._error_text, 1)
        details_btn = QPushButton("Подробнее")
        details_btn.clicked.connect(self._on_show_build_error)
        lay.addWidget(details_btn)
        return banner

    # ---------- public ----------

    def set_document(self, document: Optional[Document]) -> bool:
        self._loading = True
        try:
            self._document = document
            self._edited = None
            self._extraction = None
            self._build_error = None
            self._clear_list()
            self._supp.clear()
            self._error_banner.setVisible(False)
            self._detail_stack.setCurrentIndex(0)
            self._detail_panel.set_data(None, None, None)

            if document is None:
                return False

            # Build error (если был).
            self._build_error = _BuildErrorReport.load(document)
            if self._build_error is not None:
                self._error_text.setText(
                    f"<b>Ошибка построения графа:</b> "
                    f"{_html_escape(self._build_error.exception_type)}: "
                    f"{_html_escape(self._build_error.exception_message)}"
                )
                self._error_banner.setVisible(True)

            # DraftGraph.
            path = document.draft_graph_file_path()
            if not path.exists():
                return False
            try:
                draft = DraftGraph.load(path)
            except Exception:  # noqa: BLE001
                return False

            edits_path = document.draft_graph_edits_file_path()
            try:
                # Сигнатура: EditedGraph.load(draft, edits_path).
                # До этого был перепутан порядок → exists() падал на DraftGraph,
                # except глотал, edits отбрасывались. Теперь правильно.
                self._edited = (
                    EditedGraph.load(draft, edits_path)
                    if edits_path.exists()
                    else EditedGraph(draft)
                )
            except Exception:  # noqa: BLE001
                self._edited = EditedGraph(draft)

            try:
                self._extraction = ExtractionResult.load(document.extraction_result_file_path())
            except Exception:  # noqa: BLE001
                self._extraction = None

            supp_path = document.supplementary_facts_ttl_path()
            text = read_text_file(supp_path)
            self._supp.blockSignals(True)
            self._supp.setPlainText(text if text.strip() else self._SUPPLEMENTARY_DEFAULT)
            self._supp.blockSignals(False)

            self._rebuild_list()
            return True
        finally:
            self._loading = False

    # ---------- list ----------

    def _clear_list(self):
        self._items.clear()
        self._list_widget.clear()

    def _rebuild_list(self):
        self._clear_list()
        if self._edited is None:
            return
        for i in range(len(self._edited.draft.triples)):
            row = _TripleListItem(i, self._edited, self._nm_graph)
            row.refresh(self._extraction)
            list_item = QListWidgetItem(self._list_widget)
            self._list_widget.addItem(list_item)
            self._list_widget.setItemWidget(list_item, row)
            self._items.append(row)
        # Высоту считаем после всех addItem — viewport уже знает свою ширину.
        self._update_list_item_heights()

    def _refresh_list_items(self):
        for item in self._items:
            item.refresh(self._extraction)
        # После refresh текст мог измениться (другая длина) → пересчитать.
        self._update_list_item_heights()

    def _update_list_item_heights(self):
        avail_w = self._list_widget.viewport().width()
        if avail_w < 50 or not self._items:
            return
        for i, row in enumerate(self._items):
            list_item = self._list_widget.item(i)
            if list_item is None:
                continue
            h = row.compute_height_for_width(avail_w)
            current = list_item.sizeHint()
            if current.height() != h or current.width() != avail_w:
                list_item.setSizeHint(QSize(avail_w, h))

    def eventFilter(self, obj, event):  # noqa: N802 — Qt API
        if event.type() == QEvent.Type.Resize and obj is self._list_widget.viewport():
            self._update_list_item_heights()
        return super().eventFilter(obj, event)

    def _on_selection_changed(self):
        if self._loading:
            return
        rows = self._list_widget.selectionModel().selectedRows()
        if not rows:
            self._detail_stack.setCurrentIndex(0)
            self._detail_panel.set_data(None, None, None)
            return
        idx = rows[0].row()
        self._detail_panel.set_data(self._edited, self._extraction, idx)
        self._detail_stack.setCurrentIndex(1)

    # ---------- detail callback ----------

    def _on_detail_changed(self):
        # Что-то поменялось в правой панели — обновить список (стрипы могли
        # изменить цвет, exclude/include) и сохранить на диск.
        self._refresh_list_items()
        self._detail_panel.refresh()
        self._persist_graph()

    def _on_supp_changed(self):
        if self._loading:
            return
        self._persist_graph()

    def _persist_graph(self):
        if self._loading or self._document is None or self._edited is None:
            return
        try:
            self._edited.save(self._document.draft_graph_edits_file_path())
            self._document.supplementary_facts_ttl_path().write_text(
                self._supp.toPlainText(), encoding="utf-8"
            )
        except OSError as ex:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить: {ex}")

    # ---------- build error ----------

    def _on_show_build_error(self):
        if self._build_error is None:
            return
        dlg = _BuildErrorDialog(self._build_error, self)
        dlg.exec()
