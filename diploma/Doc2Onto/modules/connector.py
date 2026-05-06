import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from rdflib import Graph

from app.context import get_ontology_repository
from core.graph.draft_graph import EditedGraph
from models.document import Document, DocumentContext
from models.extraction_result import ExtractionResult
from modules.base import BaseModule, ModuleResult


_DATE_FIELD_PRIORITIES = (
    "application_date",
    "issue_date",
    "protocol_date",
    "instruction_date",
    "appointment_order_date",
    "practice_start_date",
    "document_date",
    "date",
)

_RU_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


class Connector(BaseModule):
    """Тонкая обёртка: применяет правки, дополнения и зовёт OntologyRepository.merge_document."""

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        if not doc.doc_class:
            return ModuleResult.failed(message="Не задан класс документа")

        draft_graph = ctx.draft_graph
        if not draft_graph:
            return ModuleResult.failed(message="Черновой граф не найден")

        try:
            edited = EditedGraph.load(draft_graph, doc.draft_graph_edits_file_path())
            modified = edited.build_modified_graph()
        except Exception as ex:
            return ModuleResult.failed(message=f"Ошибка применения правок графа: {ex}")

        if not modified.is_complete():
            return ModuleResult.failed(message="Извлечённый граф неполный")

        rdf_graph = modified.get_rdf_graph()
        if rdf_graph is None:
            return ModuleResult.failed(message="Не удалось построить RDF-граф")

        try:
            sup_path = doc.supplementary_facts_ttl_path()
            if sup_path.exists():
                sup = Graph()
                sup.parse(sup_path, format="turtle")
                for t in sup:
                    rdf_graph.add(t)
        except Exception as ex:
            return ModuleResult.failed(message=f"Не удалось разобрать дополнительные факты: {ex}")

        try:
            self._apply_reconciliation(rdf_graph)
        except Exception as ex:
            self.log(20, f"Reconciliation skipped: {ex}")

        repo = get_ontology_repository()

        try:
            existing = repo.find_history_entry(doc.id)
            history = repo.load_history_entries()
            stash_history = list(history) if existing is not None else None
            if existing is not None:
                history_no_doc = [e for e in history if e.document_id != doc.id]
                repo.save_history_entries(history_no_doc)

            try:
                snapshot = repo.assemble_full_graph()
                if not snapshot.model_valid:
                    if stash_history is not None:
                        repo.save_history_entries(stash_history)
                    return ModuleResult.failed(
                        message=f"Текущая модель некорректна до добавления документа: {snapshot.validation_message}"
                    )

                effective_date = self._extract_effective_date(ctx.extraction_result, doc)

                added_at = datetime.now(timezone.utc).isoformat()
                merge_result = repo.merge_document(
                    rdf_graph,
                    document_id=doc.id,
                    template_id=doc.doc_class,
                    component_path=doc.final_graph_file_path(),
                    effective_date=effective_date,
                    added_at=added_at,
                )
            except Exception:
                if stash_history is not None:
                    repo.save_history_entries(stash_history)
                    repo.rebuild_journal()
                raise

        except FileNotFoundError as ex:
            return ModuleResult.failed(message=str(ex))
        except RuntimeError as ex:
            return ModuleResult.failed(message=str(ex))
        except Exception as ex:
            return ModuleResult.failed(message=f"Ошибка репозитория онтологии: {ex}")

        try:
            doc.ontology_merge_report_file_path().write_text(
                json.dumps(
                    {
                        "document_id": doc.id,
                        "effective_date": effective_date,
                        "changes": [asdict(r) for r in merge_result.changes],
                        "rejected": [asdict(r) for r in merge_result.rejected],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as ex:
            self.log(30, f"Не удалось сохранить отчёт о слиянии: {ex}")

        return ModuleResult.ok()

    def _apply_reconciliation(self, rdf_graph: Graph):
        try:
            from modules.reconciler import Reconciler
        except Exception:
            return

        repo = get_ontology_repository()
        try:
            snapshot = repo.assemble_full_graph()
        except Exception:
            return

        rec = Reconciler(repo)
        rec.rewrite(rdf_graph, snapshot.graph)

    def _extract_effective_date(self, extraction_result: Optional[ExtractionResult], doc: Document) -> Optional[str]:
        """
        Находит дату документа: extraction_result -> meta -> None.
        Парсинг русских форматов: '20 декабря 2024 г.', '12.09.2025', '"29" сентября 2025 г.'.
        """
        if extraction_result is None:
            return None

        for field in _DATE_FIELD_PRIORITIES:
            value = extraction_result.get_value_final(field)
            if not value:
                continue
            iso = self._parse_russian_date(value)
            if iso:
                return iso
        return None

    @staticmethod
    def _parse_russian_date(value: str) -> Optional[str]:
        if not isinstance(value, str):
            return None
        s = value.strip().strip('"').replace("«", "").replace("»", "").strip()

        m = re.search(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b", s)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return datetime(y, mo, d).date().isoformat()
            except ValueError:
                return None

        m = re.search(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})", s)
        if m:
            d = int(m.group(1))
            month_word = m.group(2).lower()
            y = int(m.group(3))
            for prefix, mo in _RU_MONTHS.items():
                if month_word.startswith(prefix):
                    try:
                        return datetime(y, mo, d).date().isoformat()
                    except ValueError:
                        return None
        return None
