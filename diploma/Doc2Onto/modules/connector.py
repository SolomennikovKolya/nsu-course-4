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

        draft_graph = ctx.draft_graph
        if not draft_graph:
            return ModuleResult.failed(message="Черновой граф не найден")

        draft_and_edits = EditedGraph.load(draft_graph, doc.draft_graph_edits_file_path())

        moded_graph = draft_and_edits.build_modified_graph()
        if not moded_graph.is_complete():
            return ModuleResult.failed(message="Извлечённый граф неполный")

        rdf_graph = moded_graph.get_rdf_graph()
        if rdf_graph is None:
            return ModuleResult.failed(message="Не удалось построить RDF-граф из графа")

        try:
            if doc.supplementary_facts_ttl_path().exists():
                sup = Graph()
                sup.parse(doc.supplementary_facts_ttl_path(), format="turtle")
                for t in sup:
                    rdf_graph.add(t)
        except Exception as ex:
            return ModuleResult.failed(message=f"Не удалось разобрать дополнительные факты: {ex}")

        repo = get_ontology_repository()
        try:
            repo.write_ttl(rdf_graph, doc.final_graph_file_path())
        except Exception as ex:
            return ModuleResult.failed(message=f"Не удалось сохранить итоговый граф документа: {ex}")

        try:
            repo.get_schema_graph()
        except Exception as ex:
            return ModuleResult.failed(message=f"Схема онтологии недоступна: {ex}")

        try:
            old_history = repo.load_history_entries()
            old_onto = repo.assemble_full_graph(history_entries=old_history)
            if not old_onto.model_valid:
                return ModuleResult.failed(message=f"Текущая онтологическая модель некорректна до добавления документа: {old_history.validation_message}")

            history = old_history + [
                HistoryEntry(
                    document_id=doc.id,
                    template_id=doc.doc_class,
                    added_at=datetime.now(timezone.utc).isoformat(),
                    component_path=str(doc.final_graph_file_path().resolve()),
                )
            ]
            onto = repo.assemble_full_graph(history_entries=history)
            if not onto.model_valid:
                return ModuleResult.failed(message=f"После добавления фактов документа модель не проходит проверку: {onto.validation_message}")

            repo.save_history_entries(history)
            repo.write_combined_ontology(onto.merge.graph)

            doc_report = [
                asdict(r)
                for r in onto.merge.property_overwrites
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
