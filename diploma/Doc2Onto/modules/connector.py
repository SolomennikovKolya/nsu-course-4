import json
from dataclasses import asdict
from datetime import datetime, timezone
from rdflib import Graph

from app.context import get_ontology_repository
from core.graph.draft_graph import EditedGraph
from models.document import DocumentContext
from modules.base import BaseModule, ModuleResult
from storage.ontology_repository import HistoryEntry


class Connector(BaseModule):
    """Добавление триплетов в онтологическую модель."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        if not doc.doc_class:
            return ModuleResult.failed(message="Не задан класс документа")

        draft_path = doc.draft_graph_file_path()
        if not draft_path.exists():
            return ModuleResult.failed(message=f"Черновой граф не найден: {draft_path}")

        draft_graph = ctx.draft_graph
        if not draft_graph:
            return ModuleResult.failed(message="Черновой граф не найден")

        edited_graph = EditedGraph.load(draft_graph, doc.draft_graph_edits_file_path())

        modified = edited_graph.build_modified_graph()
        if not modified.is_complete():
            return ModuleResult.failed(message="Извлечённый граф неполный")

        rdf_doc = modified.get_rdf_graph()
        if rdf_doc is None:
            return ModuleResult.failed(message="Не удалось построить RDF-граф из графа")

        try:
            if doc.supplementary_facts_ttl_path().exists():
                sup = Graph()
                sup.parse(doc.supplementary_facts_ttl_path(), format="turtle")
                for t in sup:
                    rdf_doc.add(t)
        except Exception as ex:
            return ModuleResult.failed(message=f"Не удалось разобрать дополнительные факты: {ex}")

        repo = get_ontology_repository()
        try:
            repo.write_ttl(rdf_doc, doc.final_graph_file_path())
        except Exception as ex:
            return ModuleResult.failed(message=f"Не удалось сохранить итоговый граф документа: {ex}")

        try:
            repo.get_schema_graph()
        except Exception as ex:
            return ModuleResult.failed(message=f"Схема онтологии недоступна: {ex}")

        try:
            prior_entries = repo.load_history_entries()
            prior_out = repo.assemble_full_graph(history_entries=prior_entries)
            if not prior_out.model_valid:
                return ModuleResult.failed(
                    message=f"Текущая онтологическая модель некорректна до добавления документа: {prior_out.validation_message}"
                )

            component_ttl = doc.final_graph_file_path().resolve()
            candidate = HistoryEntry(
                document_id=doc.id,
                template_id=doc.doc_class,
                added_at=datetime.now(timezone.utc).isoformat(),
                component_path=str(component_ttl),
            )
            trial_entries = prior_entries + [candidate]
            trial_out = repo.assemble_full_graph(history_entries=trial_entries)
            if not trial_out.model_valid:
                return ModuleResult.failed(
                    message=f"После добавления фактов документа модель не проходит проверку: {trial_out.validation_message}"
                )

            repo.save_history_entries(trial_entries)
            repo.write_combined_ontology(trial_out.merge.graph)

            doc_report = [
                asdict(r)
                for r in trial_out.merge.property_overwrites
                if r.causing_document_id == doc.id
            ]
            doc.ontology_merge_report_file_path().write_text(
                json.dumps(
                    {"document_id": doc.id, "property_overwrites": doc_report},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        except FileNotFoundError as ex:
            return ModuleResult.failed(message=str(ex))
        except Exception as ex:
            return ModuleResult.failed(message=f"Ошибка репозитория онтологии: {ex}")

        return ModuleResult.ok()
