import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

from app.settings import ONTOLOGY_HISTORY_PATH, ONTOLOGY_PATH, ONTOLOGY_SCHEMA_PATH


@dataclass(frozen=True)
class HistoryEntry:
    """Запись о добавлении фактов документа в общую модель."""

    document_id: str     # ID документа в системе
    template_id: str     # ID шаблона, которым пользововались при извлечении
    added_at: str        # Время добавления (ISO 8601, UTC)
    component_path: str  # Абсолютный путь к компоненту знаний документа


@dataclass
class PropertyOverwriteRecord:
    """Перезапись значения из-за ограничения кардинальности (для UI)."""

    subject_n3: str
    predicate_n3: str
    removed_object_n3: str
    added_object_n3: str
    superseded_document_id: Optional[str]  # ID документа, с которого сняли старое значение (если было в модели)
    causing_document_id: str               # ID документа, чей компонент добавил новое значение и вызвал замену


@dataclass
class MergeAssemblyResult:
    """Сырой результат слияния: граф и журнал перезаписей по max-one."""

    graph: Graph                                        # Полный RDF-граф (схема + ABox после слияния)
    property_overwrites: List[PropertyOverwriteRecord]  # Перезаписи при конфликте кардинальности


@dataclass(frozen=True)
class AssembledOntology:
    """Результат сборки полной модели по списку записей истории."""

    merge: MergeAssemblyResult  # Граф и перезаписи
    model_valid: bool           # Прошла ли проверка целостности (кардинальность max-one)
    validation_message: str     # Пусто при успехе; иначе пояснение для пользователя/лога


class OntologyRepository:
    """
    Сборка и проверка онтологии по schema.ttl + компонентам из history.json.

    Состояние (оптимизация):
    - схема и max-one предикаты кэшируются
    - для неизменённого снимка истории не повторяются сборка и валидация
    """

    def __init__(self):
        self._schema_graph: Optional[Graph] = None                # TBox с диска, загружается один раз
        self._max_one_predicates: Optional[Set[URIRef]] = None    # Предикаты с «≤1 объекта» на субъекта (по схеме)
        self._assembly_cache_fingerprint: Optional[str] = None    # SHA256 от сериализованного списка HistoryEntry
        self._assembly_cache: Optional[AssembledOntology] = None  # Последняя сборка для этого отпечатка
        self._last_warmup_error: Optional[str] = None             # Краткая ошибка последнего warmup (если была)

    # --- история (history.json и записи о компонентах) ---

    def load_history_entries(self) -> List[HistoryEntry]:
        if not ONTOLOGY_HISTORY_PATH.exists():
            return []

        raw_data = json.loads(ONTOLOGY_HISTORY_PATH.read_text(encoding="utf-8"))
        items = raw_data.get("entries")
        if not isinstance(items, list):
            raise ValueError("history.json: ожидался объект с ключом entries — списком")

        history_entries: List[HistoryEntry] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"history.json: элемент {i} должен быть объектом")

            history_entries.append(
                HistoryEntry(
                    document_id=str(item["document_id"]),
                    template_id=str(item["template_id"]),
                    added_at=str(item["added_at"]),
                    component_path=str(item["component_path"]),
                )
            )
        return history_entries

    def save_history_entries(self, entries: List[HistoryEntry]):
        ONTOLOGY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [asdict(e) for e in entries],
        }
        ONTOLOGY_HISTORY_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.invalidate_assembly_cache()

    @staticmethod
    def component_file(entry: HistoryEntry) -> Path:
        return Path(entry.component_path)

    def append_history_entry(
        self,
        *,
        document_id: str,
        template_id: str,
        component_path: Path,
        added_at: Optional[datetime] = None,
    ) -> HistoryEntry:
        entries = self.load_history_entries()
        ts = added_at or datetime.now(timezone.utc)
        entry = HistoryEntry(
            document_id=document_id,
            template_id=template_id,
            added_at=ts.isoformat(),
            component_path=str(component_path.resolve()),
        )
        entries.append(entry)
        self.save_history_entries(entries)
        return entry

    def remove_last_history_entry(self) -> Optional[HistoryEntry]:
        entries = self.load_history_entries()
        if not entries:
            return None
        removed = entries.pop()
        self.save_history_entries(entries)
        return removed

    # --- схема (TBox, кэш в памяти) ---

    def get_schema_graph(self) -> Graph:
        """Загружает схему онтологии из файла."""
        if self._schema_graph is not None:
            return self._schema_graph

        if not ONTOLOGY_SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Файл схемы не найден: {ONTOLOGY_SCHEMA_PATH}")

        g = Graph()
        g.parse(ONTOLOGY_SCHEMA_PATH, format="turtle")
        self._schema_graph = g
        return g

    def get_max_one_predicates(self) -> Set[URIRef]:
        if self._max_one_predicates is not None:
            return self._max_one_predicates
        self._max_one_predicates = self._collect_max_one_predicates(self.get_schema_graph())
        return self._max_one_predicates

    @staticmethod
    def _collect_max_one_predicates(schema_graph: Graph) -> Set[URIRef]:
        out: Set[URIRef] = set()

        for p in schema_graph.subjects(RDF.type, OWL.FunctionalProperty):
            if isinstance(p, URIRef):
                out.add(p)

        for restr in schema_graph.subjects(RDF.type, OWL.Restriction):
            p = schema_graph.value(restr, OWL.onProperty)
            if not isinstance(p, URIRef):
                continue
            for owl_key in (OWL.maxCardinality, OWL.cardinality, OWL.maxQualifiedCardinality):
                val = schema_graph.value(restr, owl_key)
                if val is not None:
                    try:
                        n = int(val)
                    except (TypeError, ValueError):
                        continue
                    if n == 1:
                        out.add(p)
                        break

        return out

    # --- сборка полной модели и слияние компонентов ---

    def assemble_full_graph(self, history_entries: Optional[List[HistoryEntry]] = None) -> AssembledOntology:
        """
        Полная модель: схема (TBox) + компоненты в порядке истории.
        Для неизменённого списка записей возвращает кэшированный результат (включая флаг валидности).
        """
        entries = history_entries if history_entries is not None else self.load_history_entries()
        fp = self._history_fingerprint(entries)
        if fp == self._assembly_cache_fingerprint and self._assembly_cache is not None:
            return self._assembly_cache

        schema_g = self.get_schema_graph()
        max_one = self.get_max_one_predicates()

        combined = Graph()
        for t in schema_g:
            combined.add(t)

        provenance: Dict[Tuple, str] = {}
        overwrites: List[PropertyOverwriteRecord] = []

        for entry in entries:
            comp_path = self.component_file(entry)
            if not comp_path.is_file():
                raise FileNotFoundError(f"Компонент истории не найден: {comp_path}")

            chunk = Graph()
            chunk.parse(comp_path, format="turtle")

            for s, p, o in self._sorted_triples(chunk):
                self._merge_one_triple(
                    combined,
                    s,
                    p,
                    o,
                    max_one,
                    provenance,
                    overwrites,
                    entry.document_id,
                )

        merge = MergeAssemblyResult(graph=combined, property_overwrites=overwrites)
        ok, msg = self.validate_model(merge.graph, max_one)
        out = AssembledOntology(merge=merge, model_valid=ok, validation_message=msg)
        self._assembly_cache_fingerprint = fp
        self._assembly_cache = out
        return out

    def _sorted_triples(self, g: Graph) -> List[Tuple]:
        def key(t):
            s, p, o = t
            return (s.n3(), p.n3(), o.n3())

        return sorted(list(g), key=key)

    def _merge_one_triple(
        self,
        target: Graph,
        s,
        p,
        o,
        max_one: Set[URIRef],
        provenance: Dict[Tuple, str],
        overwrites: List[PropertyOverwriteRecord],
        source_doc_id: str,
    ):
        if (s, p, o) in target:
            return

        if isinstance(p, URIRef) and p in max_one:
            for o_old in list(target.objects(s, p)):
                triple_old = (s, p, o_old)
                prev_doc = provenance.pop(triple_old, None)
                target.remove(triple_old)
                overwrites.append(
                    PropertyOverwriteRecord(
                        subject_n3=s.n3(),
                        predicate_n3=p.n3(),
                        removed_object_n3=o_old.n3(),
                        added_object_n3=o.n3(),
                        superseded_document_id=prev_doc,
                        causing_document_id=source_doc_id,
                    )
                )

        target.add((s, p, o))
        provenance[(s, p, o)] = source_doc_id

    # --- проверка согласованности ---

    @staticmethod
    def validate_model(graph: Graph, max_one_predicates: Set[URIRef]) -> Tuple[bool, str]:
        violations: List[str] = []
        sp_seen: Dict[Tuple, int] = {}
        for s, p, o in graph:
            if not isinstance(p, URIRef) or p not in max_one_predicates:
                continue
            key = (s, p)
            sp_seen[key] = sp_seen.get(key, 0) + 1

        for (s, p), cnt in sp_seen.items():
            if cnt > 1:
                violations.append(
                    f"Нарушение кардинальности для ({s.n3()}, {p.n3()}): {cnt} объектов."
                )

        if violations:
            return False, "; ".join(violations[:20]) + (
                " …" if len(violations) > 20 else ""
            )
        return True, ""

    # --- запись RDF (Turtle) ---

    @staticmethod
    def write_ttl(graph: Graph, path: Path):
        """Сохраняет RDF-граф в Turtle-файл."""
        path.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=path, format="turtle", encoding="utf-8")

    def write_combined_ontology(self, graph: Graph):
        """Сохраняет общую модель в Turtle-файл."""
        self.write_ttl(graph, ONTOLOGY_PATH)

    # --- кэш сборки, отпечаток истории, warmup ---

    @staticmethod
    def _history_fingerprint(entries: List[HistoryEntry]) -> str:
        payload = json.dumps([asdict(e) for e in entries], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def invalidate_assembly_cache(self):
        """Сбросить кэш сборки (после правок истории или TTL вне этого класса)."""
        self._assembly_cache_fingerprint = None
        self._assembly_cache = None

    def get_cached_assembly_for_current_history(self) -> Optional[AssembledOntology]:
        """
        Если на диске тот же снимок истории, что уже был собран в кэше — вернуть кэш без пересборки.
        Иначе None (нужен вызов assemble_full_graph).
        """
        try:
            entries = self.load_history_entries()
        except Exception:
            return None
        fp = self._history_fingerprint(entries)
        if fp == self._assembly_cache_fingerprint and self._assembly_cache is not None:
            return self._assembly_cache
        return None

    def last_warmup_error(self) -> Optional[str]:
        """Ошибка последнего warmup (если была), иначе None."""
        return self._last_warmup_error

    def warmup(self, logger: logging.Logger):
        """
        Пробует загрузить схему и проверить текущую модель по history.json.
        Не бросает исключений наружу; при проблемах пишет в лог и сбрасывает кэш.
        """
        self._last_warmup_error = None

        try:
            self.get_schema_graph()
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
