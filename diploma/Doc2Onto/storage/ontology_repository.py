from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

from app.settings import (
    FACTS_JOURNAL_PATH,
    ONTOLOGY_HISTORY_PATH,
    ONTOLOGY_PATH,
    ONTOLOGY_SCHEMA_PATH,
    SUBJECT_NAMESPACE_IRI,
)

ONTO = Namespace(SUBJECT_NAMESPACE_IRI)
MERGE_POLICY = ONTO["mergePolicy"]


class MergePolicy(str, Enum):
    """Политика слияния значений предиката (см. :mergePolicy в schema.ttl)."""

    SET = "SET"                    # single-valued, неизменное (полная замена без учёта дат)
    SET_BY_DATE = "SET_BY_DATE"    # single-valued, временное (замена только если effective_date нового ≥ существующего)
    ADD = "ADD"                    # multi-valued (чистый add)


_POLICY_IRI_TO_ENUM: Dict[URIRef, MergePolicy] = {
    URIRef(SUBJECT_NAMESPACE_IRI + "Policy_Set"): MergePolicy.SET,
    URIRef(SUBJECT_NAMESPACE_IRI + "Policy_SetByDate"): MergePolicy.SET_BY_DATE,
    URIRef(SUBJECT_NAMESPACE_IRI + "Policy_Add"): MergePolicy.ADD,
}

DEFAULT_POLICY = MergePolicy.ADD


@dataclass(frozen=True)
class HistoryEntry:
    """Запись о добавлении фактов документа в общую модель."""

    document_id: str                            # ID документа в системе
    template_id: str                            # ID шаблона
    added_at: str                               # Время добавления (ISO 8601, UTC)
    component_path: str                         # Путь к фрагменту RDF (rdf.ttl документа)
    effective_date: Optional[str] = None        # Дата, к которой относятся факты (ISO 8601 date), может быть None


@dataclass
class FactChangeRecord:
    """Изменение, произведённое одним документом при слиянии (для UI)."""

    event: str                                  # "added" | "replaced" | "superseded_by_existing" | "rejected_older"
    subject_n3: str
    predicate_n3: str
    object_n3: str
    policy: str
    effective_date: Optional[str] = None
    superseded_object_n3: Optional[str] = None  # для replaced: какое значение убрали
    superseded_doc_id: Optional[str] = None     # документ, чьим значением было replaced


@dataclass
class FactEvent:
    """Событие журнала фактов (один лог-элемент в facts.jsonl)."""

    event: str                                  # "add" | "retract" | "reject"
    s: str
    p: str
    o: str
    doc_id: Optional[str] = None
    template_id: Optional[str] = None
    policy: Optional[str] = None
    effective_date: Optional[str] = None
    added_at: Optional[str] = None
    active: Optional[bool] = None
    cause_doc_id: Optional[str] = None          # для retract — документ, добивший этот факт
    reason: Optional[str] = None
    retracted_at: Optional[str] = None


@dataclass
class MergeDocumentResult:
    """Результат merge одного документа в активный граф."""

    changes: List[FactChangeRecord] = field(default_factory=list)
    rejected: List[FactChangeRecord] = field(default_factory=list)


@dataclass(frozen=True)
class AssembledOntology:
    """Результат сборки полной модели по списку записей истории."""

    graph: Graph                    # Полный RDF-граф (схема + ABox после слияния)
    model_valid: bool               # Прошла ли проверка целостности
    validation_message: str         # Пусто при успехе; иначе пояснение ошибки
    fact_events: List[FactEvent] = field(default_factory=list)  # События, накопленные при сборке


class OntologyRepository:
    """
    Хранение и сборка онтологии:
      - schema.ttl как TBox (read-only из resources/onto/);
      - history.json как список добавленных документов (source of truth для ABox);
      - facts.jsonl как append-only журнал событий слияния (derived index).

    Алгоритм слияния задаётся не функциональностью свойств, а аннотацией :mergePolicy
    в схеме (см. MergePolicy).
    """

    def __init__(self):
        self._schema_graph: Optional[Graph] = None
        self._policies: Optional[Dict[URIRef, MergePolicy]] = None
        self._assembly_cache_fingerprint: Optional[str] = None
        self._assembly_cache: Optional[AssembledOntology] = None
        self._last_warmup_error: Optional[str] = None

    # =================================================================
    # Схема и политики (TBox)
    # =================================================================

    def get_schema_graph(self) -> Graph:
        if self._schema_graph is not None:
            return self._schema_graph

        if not ONTOLOGY_SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Файл схемы не найден: {ONTOLOGY_SCHEMA_PATH}")

        g = Graph()
        g.parse(ONTOLOGY_SCHEMA_PATH, format="turtle")
        self._schema_graph = g
        return g

    def load_merge_policies(self) -> Dict[URIRef, MergePolicy]:
        """Возвращает {predicate -> MergePolicy} по аннотациям :mergePolicy схемы."""
        if self._policies is not None:
            return self._policies

        out: Dict[URIRef, MergePolicy] = {}
        schema = self.get_schema_graph()
        for predicate, policy_iri in schema.subject_objects(MERGE_POLICY):
            if not isinstance(predicate, URIRef) or not isinstance(policy_iri, URIRef):
                continue
            policy = _POLICY_IRI_TO_ENUM.get(policy_iri)
            if policy is None:
                continue
            out[predicate] = policy

        out[RDF.type] = MergePolicy.ADD
        self._policies = out
        return out

    def get_policy(self, predicate: URIRef) -> MergePolicy:
        return self.load_merge_policies().get(predicate, DEFAULT_POLICY)

    # =================================================================
    # История (history.json)
    # =================================================================

    def load_history_entries(self) -> List[HistoryEntry]:
        if not ONTOLOGY_HISTORY_PATH.exists():
            return []

        text = ONTOLOGY_HISTORY_PATH.read_text(encoding="utf-8").strip()
        if not text:
            return []

        raw_data = json.loads(text)
        items = raw_data.get("entries")
        if not isinstance(items, list):
            raise ValueError("history.json: ожидался объект с ключом entries — списком")

        out: List[HistoryEntry] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"history.json: элемент {i} должен быть объектом")
            out.append(
                HistoryEntry(
                    document_id=str(item["document_id"]),
                    template_id=str(item["template_id"]),
                    added_at=str(item["added_at"]),
                    component_path=str(item["component_path"]),
                    effective_date=item.get("effective_date"),
                )
            )
        return out

    def save_history_entries(self, entries: List[HistoryEntry]):
        ONTOLOGY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": [asdict(e) for e in entries]}
        ONTOLOGY_HISTORY_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.invalidate_assembly_cache()

    @staticmethod
    def component_file(entry: HistoryEntry) -> Path:
        return Path(entry.component_path)

    def find_history_entry(self, document_id: str) -> Optional[HistoryEntry]:
        for e in self.load_history_entries():
            if e.document_id == document_id:
                return e
        return None

    # =================================================================
    # Журнал фактов (facts.jsonl, derived index)
    # =================================================================

    @staticmethod
    def _journal_path() -> Path:
        return FACTS_JOURNAL_PATH

    @classmethod
    def read_journal(cls) -> List[FactEvent]:
        path = cls._journal_path()
        if not path.exists():
            return []
        out: List[FactEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            try:
                out.append(FactEvent(**{k: obj.get(k) for k in FactEvent.__dataclass_fields__}))
            except Exception:
                continue
        return out

    @classmethod
    def _append_journal_events(cls, events: Iterable[FactEvent]):
        events = list(events)
        if not events:
            return
        path = cls._journal_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(asdict(ev), ensure_ascii=False))
                f.write("\n")

    @classmethod
    def journal_for_subject(cls, subject: URIRef | str) -> List[FactEvent]:
        s_n3 = subject.n3() if isinstance(subject, URIRef) else str(subject)
        return [ev for ev in cls.read_journal() if ev.s == s_n3]

    @classmethod
    def journal_active_facts_index(cls) -> Dict[Tuple[str, str, str], FactEvent]:
        """
        Сворачивает журнал в индекс активных фактов: {(s, p, o) -> последний add-event с active=True}.
        retract обнуляет active.
        """
        out: Dict[Tuple[str, str, str], FactEvent] = {}
        for ev in cls.read_journal():
            key = (ev.s, ev.p, ev.o)
            if ev.event == "add":
                out[key] = ev
            elif ev.event == "retract":
                if key in out:
                    out.pop(key)
            # reject не влияет на активность
        return out

    # =================================================================
    # Сборка полной модели (TBox + ABox по истории)
    # =================================================================

    def assemble_full_graph(
        self,
        history_entries: Optional[List[HistoryEntry]] = None,
    ) -> AssembledOntology:
        """
        Полная модель: схема + ABox, собранный из фрагментов истории по их порядку,
        с учётом политик слияния и effective_date.
        """
        entries = history_entries if history_entries is not None else self.load_history_entries()
        fp = self._history_fingerprint(entries)
        if fp == self._assembly_cache_fingerprint and self._assembly_cache is not None:
            return self._assembly_cache

        schema_g = self.get_schema_graph()
        policies = self.load_merge_policies()

        combined = Graph()
        for t in schema_g:
            combined.add(t)

        # Вспомогательное состояние:
        #  - provenance[(s,p,o)] = (doc_id, effective_date)
        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]] = {}
        all_events: List[FactEvent] = []

        for entry in entries:
            comp_path = self.component_file(entry)
            if not comp_path.is_file():
                raise FileNotFoundError(f"Компонент истории не найден: {comp_path}")

            chunk = Graph()
            chunk.parse(comp_path, format="turtle")

            self._merge_chunk_into_active(
                active=combined,
                chunk=chunk,
                provenance=provenance,
                policies=policies,
                doc_id=entry.document_id,
                template_id=entry.template_id,
                effective_date=entry.effective_date,
                added_at=entry.added_at,
                events_out=all_events,
            )

        ok, msg = self.validate_model(combined, policies)
        out = AssembledOntology(
            graph=combined,
            model_valid=ok,
            validation_message=msg,
            fact_events=all_events,
        )
        self._assembly_cache_fingerprint = fp
        self._assembly_cache = out
        return out

    def _merge_chunk_into_active(
        self,
        *,
        active: Graph,
        chunk: Graph,
        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]],
        policies: Dict[URIRef, MergePolicy],
        doc_id: str,
        template_id: str,
        effective_date: Optional[str],
        added_at: str,
        events_out: List[FactEvent],
    ) -> MergeDocumentResult:
        """
        Применяет триплеты chunk к active с учётом политик и журналирует события.
        Возвращает суммарные изменения по конкретному документу.
        """
        result = MergeDocumentResult()

        for s, p, o in self._sorted_triples(chunk):
            policy = policies.get(p, DEFAULT_POLICY) if isinstance(p, URIRef) else DEFAULT_POLICY
            self._apply_one_triple(
                active=active,
                s=s, p=p, o=o,
                policy=policy,
                provenance=provenance,
                doc_id=doc_id,
                template_id=template_id,
                effective_date=effective_date,
                added_at=added_at,
                events_out=events_out,
                result=result,
            )

        return result

    def _apply_one_triple(
        self,
        *,
        active: Graph,
        s: Node,
        p: Node,
        o: Node,
        policy: MergePolicy,
        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]],
        doc_id: str,
        template_id: str,
        effective_date: Optional[str],
        added_at: str,
        events_out: List[FactEvent],
        result: MergeDocumentResult,
    ):
        triple = (s, p, o)
        existing_objects = list(active.objects(s, p))

        if triple in active:
            return

        if policy == MergePolicy.ADD:
            self._add_fact(
                active, s, p, o,
                doc_id=doc_id, template_id=template_id,
                policy=policy, effective_date=effective_date, added_at=added_at,
                provenance=provenance, events_out=events_out, result=result,
            )
            return

        if policy == MergePolicy.SET:
            for o_old in existing_objects:
                self._retract_fact(
                    active, s, p, o_old,
                    cause_doc_id=doc_id,
                    reason="superseded_by_set",
                    provenance=provenance, events_out=events_out,
                    result_replaced_for=(s, p, o),
                    result=result,
                )
            self._add_fact(
                active, s, p, o,
                doc_id=doc_id, template_id=template_id,
                policy=policy, effective_date=effective_date, added_at=added_at,
                provenance=provenance, events_out=events_out, result=result,
            )
            return

        if policy == MergePolicy.SET_BY_DATE:
            if not existing_objects:
                self._add_fact(
                    active, s, p, o,
                    doc_id=doc_id, template_id=template_id,
                    policy=policy, effective_date=effective_date, added_at=added_at,
                    provenance=provenance, events_out=events_out, result=result,
                )
                return

            new_date = effective_date or ""
            should_replace = False
            superseded_for: List[Tuple[Node, str]] = []
            for o_old in existing_objects:
                old_date = (provenance.get((s, p, o_old), (doc_id, None))[1]) or ""
                if new_date >= old_date:
                    should_replace = True
                    superseded_for.append((o_old, old_date))

            if should_replace:
                for o_old, _ in superseded_for:
                    self._retract_fact(
                        active, s, p, o_old,
                        cause_doc_id=doc_id,
                        reason="superseded_by_newer",
                        provenance=provenance, events_out=events_out,
                        result_replaced_for=(s, p, o),
                        result=result,
                    )
                self._add_fact(
                    active, s, p, o,
                    doc_id=doc_id, template_id=template_id,
                    policy=policy, effective_date=effective_date, added_at=added_at,
                    provenance=provenance, events_out=events_out, result=result,
                )
            else:
                events_out.append(FactEvent(
                    event="reject",
                    s=s.n3(), p=p.n3(), o=o.n3(),
                    doc_id=doc_id,
                    template_id=template_id,
                    policy=policy.value,
                    effective_date=effective_date,
                    added_at=added_at,
                    reason="older_than_existing",
                ))
                result.rejected.append(FactChangeRecord(
                    event="superseded_by_existing",
                    subject_n3=s.n3(),
                    predicate_n3=p.n3(),
                    object_n3=o.n3(),
                    policy=policy.value,
                    effective_date=effective_date,
                ))

    @staticmethod
    def _add_fact(
        active: Graph, s: Node, p: Node, o: Node,
        *,
        doc_id: str, template_id: str,
        policy: MergePolicy,
        effective_date: Optional[str],
        added_at: str,
        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]],
        events_out: List[FactEvent],
        result: MergeDocumentResult,
    ):
        active.add((s, p, o))
        provenance[(s, p, o)] = (doc_id, effective_date)
        events_out.append(FactEvent(
            event="add",
            s=s.n3(), p=p.n3(), o=o.n3(),
            doc_id=doc_id,
            template_id=template_id,
            policy=policy.value,
            effective_date=effective_date,
            added_at=added_at,
            active=True,
        ))
        result.changes.append(FactChangeRecord(
            event="added",
            subject_n3=s.n3(),
            predicate_n3=p.n3(),
            object_n3=o.n3(),
            policy=policy.value,
            effective_date=effective_date,
        ))

    @staticmethod
    def _retract_fact(
        active: Graph, s: Node, p: Node, o: Node,
        *,
        cause_doc_id: str,
        reason: str,
        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]],
        events_out: List[FactEvent],
        result_replaced_for: Optional[Tuple[Node, Node, Node]],
        result: MergeDocumentResult,
    ):
        active.remove((s, p, o))
        prev = provenance.pop((s, p, o), None)
        events_out.append(FactEvent(
            event="retract",
            s=s.n3(), p=p.n3(), o=o.n3(),
            cause_doc_id=cause_doc_id,
            reason=reason,
            retracted_at=datetime.now(timezone.utc).isoformat(),
        ))
        if result_replaced_for is not None:
            ns, np, no = result_replaced_for
            result.changes.append(FactChangeRecord(
                event="replaced",
                subject_n3=ns.n3(),
                predicate_n3=np.n3(),
                object_n3=no.n3(),
                policy=MergePolicy.SET.value,
                superseded_object_n3=o.n3(),
                superseded_doc_id=prev[0] if prev else None,
            ))

    @staticmethod
    def _sorted_triples(g: Graph) -> List[Tuple[Node, Node, Node]]:
        return sorted(list(g), key=lambda t: (t[0].n3(), t[1].n3(), t[2].n3()))

    # =================================================================
    # Слияние одного документа в текущий граф (с журналированием)
    # =================================================================

    def merge_document(
        self,
        rdf_graph: Graph,
        *,
        document_id: str,
        template_id: str,
        component_path: Path,
        effective_date: Optional[str] = None,
        added_at: Optional[str] = None,
    ) -> MergeDocumentResult:
        """
        Полный путь добавления документа в модель:
          1. Сохранить переданный фрагмент как rdf.ttl документа (если ещё не он сам).
          2. Дописать HistoryEntry в history.json (если документа там ещё нет).
          3. Пересобрать полный граф и журнал; результат изменений по этому документу — в возврат.
        Идемпотентно: повторный merge документа c тем же id не дублирует историю и события.
        """
        ts = added_at or datetime.now(timezone.utc).isoformat()

        component_path = Path(component_path)
        component_path.parent.mkdir(parents=True, exist_ok=True)
        rdf_graph.serialize(destination=component_path, format="turtle", encoding="utf-8")

        history = self.load_history_entries()
        existing = next((e for e in history if e.document_id == document_id), None)

        if existing is None:
            entry = HistoryEntry(
                document_id=document_id,
                template_id=template_id,
                added_at=ts,
                component_path=str(component_path.resolve()),
                effective_date=effective_date,
            )
            history.append(entry)
        else:
            entry = HistoryEntry(
                document_id=document_id,
                template_id=template_id,
                added_at=existing.added_at,
                component_path=str(component_path.resolve()),
                effective_date=effective_date if effective_date is not None else existing.effective_date,
            )
            history = [entry if e.document_id == document_id else e for e in history]

        self.save_history_entries(history)
        self.rebuild_journal()
        full = self.assemble_full_graph(history)
        if not full.model_valid:
            raise RuntimeError(f"После слияния модель не прошла валидацию: {full.validation_message}")

        self.write_combined_ontology(full.graph)

        return self._extract_doc_changes(full.fact_events, document_id)

    @staticmethod
    def _extract_doc_changes(events: List[FactEvent], document_id: str) -> MergeDocumentResult:
        """Восстанавливает FactChangeRecord-ы только для конкретного документа из общего лога событий."""
        result = MergeDocumentResult()
        retracted_index: Dict[Tuple[str, str], List[FactEvent]] = {}
        for ev in events:
            if ev.event == "retract" and ev.cause_doc_id == document_id:
                retracted_index.setdefault((ev.s, ev.p), []).append(ev)

        for ev in events:
            if ev.event == "add" and ev.doc_id == document_id:
                replaced = retracted_index.get((ev.s, ev.p), [])
                if replaced:
                    for r in replaced:
                        result.changes.append(FactChangeRecord(
                            event="replaced",
                            subject_n3=ev.s,
                            predicate_n3=ev.p,
                            object_n3=ev.o,
                            policy=ev.policy or "",
                            effective_date=ev.effective_date,
                            superseded_object_n3=r.o,
                            superseded_doc_id=None,
                        ))
                else:
                    result.changes.append(FactChangeRecord(
                        event="added",
                        subject_n3=ev.s,
                        predicate_n3=ev.p,
                        object_n3=ev.o,
                        policy=ev.policy or "",
                        effective_date=ev.effective_date,
                    ))
            elif ev.event == "reject" and ev.doc_id == document_id:
                result.rejected.append(FactChangeRecord(
                    event="superseded_by_existing",
                    subject_n3=ev.s,
                    predicate_n3=ev.p,
                    object_n3=ev.o,
                    policy=ev.policy or "",
                    effective_date=ev.effective_date,
                ))
        return result

    # =================================================================
    # Откат документа
    # =================================================================

    def rollback_document(self, document_id: str) -> bool:
        """
        Снимает HistoryEntry с заданным document_id, пересобирает граф и журнал.
        Возвращает True, если документ был в истории, False — иначе.
        """
        history = self.load_history_entries()
        new_history = [e for e in history if e.document_id != document_id]
        if len(new_history) == len(history):
            return False

        self.save_history_entries(new_history)
        self.rebuild_journal()
        full = self.assemble_full_graph(new_history)
        self.write_combined_ontology(full.graph)
        return True

    # =================================================================
    # Полная пересборка журнала
    # =================================================================

    def rebuild_journal(self):
        """
        Стирает facts.jsonl и заново прогоняет все фрагменты в порядке history.json
        через слияние; журнал пишется по ходу.
        """
        path = self._journal_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        history = self.load_history_entries()
        self.invalidate_assembly_cache()

        try:
            schema_g = self.get_schema_graph()
        except Exception:
            return

        policies = self.load_merge_policies()
        active = Graph()
        for t in schema_g:
            active.add(t)

        provenance: Dict[Tuple[Node, Node, Node], Tuple[str, Optional[str]]] = {}

        tmp_fd, tmp_name = tempfile.mkstemp(prefix="facts_", suffix=".jsonl", dir=str(path.parent))
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                for entry in history:
                    comp_path = self.component_file(entry)
                    if not comp_path.is_file():
                        continue
                    chunk = Graph()
                    chunk.parse(comp_path, format="turtle")

                    events: List[FactEvent] = []
                    self._merge_chunk_into_active(
                        active=active,
                        chunk=chunk,
                        provenance=provenance,
                        policies=policies,
                        doc_id=entry.document_id,
                        template_id=entry.template_id,
                        effective_date=entry.effective_date,
                        added_at=entry.added_at,
                        events_out=events,
                    )
                    for ev in events:
                        f.write(json.dumps(asdict(ev), ensure_ascii=False))
                        f.write("\n")

            shutil.move(tmp_name, path)
        except Exception:
            if Path(tmp_name).exists():
                try:
                    Path(tmp_name).unlink()
                except Exception:
                    pass
            raise

    # =================================================================
    # Валидация
    # =================================================================

    @staticmethod
    def validate_model(graph: Graph, policies: Dict[URIRef, MergePolicy]) -> Tuple[bool, str]:
        """
        Single-valued (SET, SET_BY_DATE) предикаты — не больше одного объекта на (s, p)
        в активном графе. Для ADD ограничения нет.
        """
        violations: List[str] = []
        sp_seen: Dict[Tuple[Node, Node], int] = {}

        for s, p, _ in graph:
            if not isinstance(p, URIRef):
                continue
            pol = policies.get(p, DEFAULT_POLICY)
            if pol == MergePolicy.ADD:
                continue
            key = (s, p)
            sp_seen[key] = sp_seen.get(key, 0) + 1

        for (s, p), cnt in sp_seen.items():
            if cnt > 1:
                violations.append(
                    f"Нарушение single-valued ({policies.get(p).value}) для ({s.n3()}, {p.n3()}): {cnt} объектов."
                )

        if violations:
            return False, "; ".join(violations[:20]) + (" …" if len(violations) > 20 else "")
        return True, ""

    # =================================================================
    # Запись TTL
    # =================================================================

    @staticmethod
    def write_ttl(graph: Graph, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=path, format="turtle", encoding="utf-8")

    def write_combined_ontology(self, graph: Graph):
        self.write_ttl(graph, ONTOLOGY_PATH)

    # =================================================================
    # Кэш / отпечаток / warmup
    # =================================================================

    @staticmethod
    def _history_fingerprint(entries: List[HistoryEntry]) -> str:
        payload = json.dumps([asdict(e) for e in entries], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def invalidate_assembly_cache(self):
        self._assembly_cache_fingerprint = None
        self._assembly_cache = None

    def get_cached_assembly_for_current_history(self) -> Optional[AssembledOntology]:
        try:
            entries = self.load_history_entries()
        except Exception:
            return None
        fp = self._history_fingerprint(entries)
        if fp == self._assembly_cache_fingerprint and self._assembly_cache is not None:
            return self._assembly_cache
        return None

    def last_warmup_error(self) -> Optional[str]:
        return self._last_warmup_error

    def warmup(self, logger: logging.Logger):
        self._last_warmup_error = None

        try:
            self.get_schema_graph()
            self.load_merge_policies()
        except Exception as ex:
            self._last_warmup_error = f"схема: {ex}"
            logger.warning("[OntologyRepository] Не удалось загрузить схему: %s", ex)
            self.invalidate_assembly_cache()
            return

        try:
            ONTOLOGY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            entries = self.load_history_entries()
            self.assemble_full_graph(entries)
        except Exception as ex:
            self._last_warmup_error = f"модель: {ex}"
            logger.warning("[OntologyRepository] Проверка текущей модели при старте: %s", ex)
            self.invalidate_assembly_cache()
