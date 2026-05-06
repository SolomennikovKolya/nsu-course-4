from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

from app.settings import SUBJECT_NAMESPACE_IRI


_NS = SUBJECT_NAMESPACE_IRI

# --- Классы, по которым делается reconciliation ---

PERSON_CLASSES: Set[URIRef] = {
    URIRef(_NS + "Персона"),
    URIRef(_NS + "Студент"),
    URIRef(_NS + "Сотрудник"),
}
ORGANIZATION_CLASSES: Set[URIRef] = {
    URIRef(_NS + "Организация"),
    URIRef(_NS + "Университет"),
    URIRef(_NS + "СтруктурноеПодразделение"),
    URIRef(_NS + "Факультет"),
    URIRef(_NS + "Кафедра"),
    URIRef(_NS + "Лаборатория"),
    URIRef(_NS + "ВнешняяОрганизация"),
}
PROFILE_CLASSES: Set[URIRef] = {URIRef(_NS + "Профиль")}
THESIS_CLASSES: Set[URIRef] = {URIRef(_NS + "ВКР")}

# --- Предикаты ---

P_LAST_NAME = URIRef(_NS + "фамилия")
P_FIRST_NAME = URIRef(_NS + "имя")
P_MIDDLE_NAME = URIRef(_NS + "отчество")
P_ORG_NAME = URIRef(_NS + "названиеОрганизации")
P_PROFILE_NAME = URIRef(_NS + "названиеПрофиля")
P_THESIS_AUTHOR = URIRef(_NS + "авторВКР")


@dataclass
class ReconcileReport:
    rewritten: Dict[str, str] = field(default_factory=dict)               # old_iri -> new_iri
    ambiguous: List[Tuple[str, List[str]]] = field(default_factory=list)  # (old_iri, [candidates])
    unmatched: List[str] = field(default_factory=list)


class Reconciler:
    """
    Перенаправляет «хешевые» индивиды извлечённого графа на канонические IRI существующих
    в основном графе. Срабатывает только в случае однозначного матча по natural-key литералам.

    Не входит в Pipeline стадией — вызывается изнутри Connector в момент, когда уже применены
    правки пользователя и доступен снимок активного графа.
    """

    def __init__(self, ontology_repository=None, logger: Optional[logging.Logger] = None):
        self._repo = ontology_repository
        self._logger = logger

    def rewrite(self, draft_graph: Graph, snapshot_graph: Graph) -> ReconcileReport:
        report = ReconcileReport()

        plan: Dict[URIRef, URIRef] = {}

        for iri, classes in self._collect_typed_individuals(draft_graph):
            new_iri = self._resolve(iri, classes, draft_graph, snapshot_graph, report)
            if new_iri is not None and new_iri != iri:
                plan[iri] = new_iri

        if plan:
            self._apply_plan(draft_graph, plan)
            for old, new in plan.items():
                report.rewritten[str(old)] = str(new)

        return report

    @staticmethod
    def _collect_typed_individuals(g: Graph) -> List[Tuple[URIRef, Set[URIRef]]]:
        index: Dict[URIRef, Set[URIRef]] = {}
        for s, _, o in g.triples((None, RDF.type, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                index.setdefault(s, set()).add(o)
        return list(index.items())

    def _resolve(
        self,
        iri: URIRef,
        classes: Set[URIRef],
        draft: Graph,
        snapshot: Graph,
        report: ReconcileReport,
    ) -> Optional[URIRef]:
        if classes & PERSON_CLASSES:
            return self._resolve_person(iri, draft, snapshot, report)
        if classes & ORGANIZATION_CLASSES:
            return self._resolve_organization(iri, draft, snapshot, report)
        if classes & PROFILE_CLASSES:
            return self._resolve_profile(iri, draft, snapshot, report)
        if classes & THESIS_CLASSES:
            return self._resolve_thesis(iri, draft, snapshot, report)
        return None

    # ------------------------------------------------------------ Person

    def _resolve_person(
        self,
        iri: URIRef,
        draft: Graph,
        snapshot: Graph,
        report: ReconcileReport,
    ) -> Optional[URIRef]:
        last = self._first_string(draft, iri, P_LAST_NAME)
        first = self._first_string(draft, iri, P_FIRST_NAME)
        middle = self._first_string(draft, iri, P_MIDDLE_NAME)

        if not last or not first:
            return None

        last_n = last.strip().lower().replace("ё", "е")
        first_n = first.strip().lower().replace("ё", "е")
        middle_n = (middle or "").strip().lower().replace("ё", "е")
        first_init = first_n[:1] if first_n else ""
        middle_init = middle_n[:1] if middle_n else ""

        candidates: List[URIRef] = []
        for s in snapshot.subjects(P_LAST_NAME, None):
            if not isinstance(s, URIRef) or s == iri:
                continue
            if any(t in PERSON_CLASSES for t in self._types_of(snapshot, s)) is False:
                pass

            cand_last = self._first_string(snapshot, s, P_LAST_NAME)
            if not cand_last:
                continue
            if cand_last.strip().lower().replace("ё", "е") != last_n:
                continue

            cand_first = self._first_string(snapshot, s, P_FIRST_NAME)
            cand_middle = self._first_string(snapshot, s, P_MIDDLE_NAME)
            cand_first_n = (cand_first or "").strip().lower().replace("ё", "е")
            cand_middle_n = (cand_middle or "").strip().lower().replace("ё", "е")

            if not self._match_name(first_n, cand_first_n, first_init):
                continue
            if not self._match_middle(middle_n, cand_middle_n, middle_init):
                continue

            candidates.append(s)

        return self._select_unique_candidate(iri, candidates, report)

    @staticmethod
    def _match_name(new_full: str, cand_full: str, new_init: str) -> bool:
        if not cand_full:
            return False
        if new_full == cand_full:
            return True
        if new_init and (cand_full.startswith(new_init) or new_full.startswith(cand_full[:1])):
            return True
        return False

    @staticmethod
    def _match_middle(new_full: str, cand_full: str, new_init: str) -> bool:
        if not new_full and not cand_full:
            return True
        if not new_full or not cand_full:
            return True
        if new_full == cand_full:
            return True
        if new_init and (cand_full.startswith(new_init) or new_full.startswith(cand_full[:1])):
            return True
        return False

    # ------------------------------------------------------------ Organization

    def _resolve_organization(self, iri, draft, snapshot, report) -> Optional[URIRef]:
        names = {self._normalize_org(n) for n in self._all_strings(draft, iri, P_ORG_NAME) if n}
        if not names:
            return None

        candidates: Set[URIRef] = set()
        for s, _, o in snapshot.triples((None, P_ORG_NAME, None)):
            if not isinstance(s, URIRef) or s == iri:
                continue
            if not isinstance(o, Literal):
                continue
            if self._normalize_org(str(o)) in names:
                candidates.add(s)

        return self._select_unique_candidate(iri, list(candidates), report)

    @staticmethod
    def _normalize_org(value: str) -> str:
        if not value:
            return ""
        text = value.strip().lower().replace("ё", "е")
        for ch in '«»"\'':
            text = text.replace(ch, "")
        text = " ".join(text.split())
        return text

    # ------------------------------------------------------------ Profile

    def _resolve_profile(self, iri, draft, snapshot, report) -> Optional[URIRef]:
        name = self._first_string(draft, iri, P_PROFILE_NAME)
        if not name:
            return None
        target = " ".join(name.strip().lower().replace("ё", "е").split())

        candidates: Set[URIRef] = set()
        for s, _, o in snapshot.triples((None, P_PROFILE_NAME, None)):
            if not isinstance(s, URIRef) or s == iri:
                continue
            if not isinstance(o, Literal):
                continue
            cand = " ".join(str(o).strip().lower().replace("ё", "е").split())
            if cand == target:
                candidates.add(s)

        return self._select_unique_candidate(iri, list(candidates), report)

    # ------------------------------------------------------------ Thesis

    def _resolve_thesis(self, iri, draft, snapshot, report) -> Optional[URIRef]:
        author = next(iter(draft.objects(iri, P_THESIS_AUTHOR)), None)
        if not isinstance(author, URIRef):
            return None

        candidates: Set[URIRef] = set()
        for s in snapshot.subjects(P_THESIS_AUTHOR, author):
            if isinstance(s, URIRef) and s != iri:
                candidates.add(s)

        return self._select_unique_candidate(iri, list(candidates), report)

    # ------------------------------------------------------------ helpers

    def _select_unique_candidate(self, iri, candidates, report) -> Optional[URIRef]:
        if not candidates:
            report.unmatched.append(str(iri))
            return None
        if len(candidates) > 1:
            report.ambiguous.append((str(iri), [str(c) for c in candidates]))
            self._warn(
                f"Reconciler: для {iri} найдено {len(candidates)} кандидатов, "
                f"объединение не выполняется"
            )
            return None
        return candidates[0]

    @staticmethod
    def _first_string(g: Graph, s: Node, p: Node) -> Optional[str]:
        for o in g.objects(s, p):
            if isinstance(o, Literal):
                return str(o)
        return None

    @staticmethod
    def _all_strings(g: Graph, s: Node, p: Node) -> List[str]:
        return [str(o) for o in g.objects(s, p) if isinstance(o, Literal)]

    @staticmethod
    def _types_of(g: Graph, s: Node) -> Set[URIRef]:
        out: Set[URIRef] = set()
        for o in g.objects(s, RDF.type):
            if isinstance(o, URIRef):
                out.add(o)
        return out

    @staticmethod
    def _apply_plan(g: Graph, plan: Dict[URIRef, URIRef]):
        replacements: List[Tuple[Tuple[Node, Node, Node], Tuple[Node, Node, Node]]] = []
        for s, p, o in g:
            ns = plan.get(s, s) if isinstance(s, URIRef) else s
            no = plan.get(o, o) if isinstance(o, URIRef) else o
            if ns is not s or no is not o:
                replacements.append(((s, p, o), (ns, p, no)))
        for old, new in replacements:
            g.remove(old)
            g.add(new)

    def _warn(self, msg: str):
        if self._logger is not None:
            self._logger.warning(msg)
