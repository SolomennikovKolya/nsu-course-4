"""
Стадия GraphBuilder — построение чернового RDF-графа из значений полей.

Что делает:
  1. Берёт нормализованные значения полей из ``ctx.extraction_result``.
  2. Создаёт :class:`TemplateGraphBuilder` и вызывает пользовательский
     ``code.build(b)`` шаблона.
  3. Сохраняет полученный :class:`DraftGraph` в ``draft_graph.json``.

Диагностика:
  * Логирует сводку до и после: сколько полей, сколько из них нормализовано,
    сколько триплетов получилось, сколько из них неполных.
  * Группирует ошибки нод по тексту и по полю-источнику — это даёт
    понятную картину «что пошло не так на стадии сборки».
  * При исключении в ``code.build(b)`` сохраняет частично построенный
    граф (то, что пользовательский код успел положить) и пишет
    отдельный ``build_error.json`` с traceback и контекстом — чтобы
    автор шаблона мог быстро понять, на каком вызове упало.
"""
from __future__ import annotations

import json
import traceback
from collections import Counter
from datetime import datetime
from logging import ERROR, INFO, WARNING
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.graph.draft_graph import DraftGraph, DraftTriple
from core.graph.template_graph_builder import TemplateGraphBuilder
from models.document import DocumentContext
from modules.base import BaseModule, ModuleResult


class GraphBuilder(BaseModule):
    """Построение чернового RDF-графа."""

    def __init__(self):
        super().__init__()

    def execute(self, ctx: DocumentContext) -> ModuleResult:
        doc = ctx.document

        tctx = ctx.template_ctx
        if not tctx:
            return ModuleResult.failed(message="Не удалось загрузить шаблон")

        fields = tctx.fields
        if not fields:
            return ModuleResult.failed(message="Шаблон не имеет полей")

        extr_res = ctx.extraction_result
        if not extr_res:
            return ModuleResult.failed(message="Не удалось загрузить результат извлечения")

        # GraphBuilder работает только с нормализованными значениями: если
        # нормализатор отверг поле — оно в граф не попадает (None в словаре
        # инициирует «неполный» DraftNode с понятной ошибкой источника).
        field_values = {f.name: extr_res.get_value_normalized(f.name) for f in fields}
        normalized_count = sum(1 for v in field_values.values() if v is not None and str(v).strip())
        empty_fields = [name for name, v in field_values.items() if not v or not str(v).strip()]

        self.log(
            INFO,
            f"Старт сборки: шаблон '{tctx.template.name}', "
            f"полей всего {len(fields)}, нормализовано {normalized_count}",
        )
        if empty_fields:
            self.log(
                INFO,
                f"Поля без нормализованного значения ({len(empty_fields)}): "
                + ", ".join(empty_fields),
            )

        builder = TemplateGraphBuilder(field_values)

        # Чистим прошлый отчёт об ошибке — теперь либо сохраним новый, либо
        # совсем уберём (пайплайн прошёл успешно).
        if doc.build_error_file_path().exists():
            doc.build_error_file_path().unlink()

        try:
            tctx.code.build(builder)
        except Exception as ex:  # noqa: BLE001 — пользовательский код, ошибка должна попасть в отчёт
            return self._handle_build_exception(ctx, builder, ex, normalized_count, empty_fields)

        # Сохраняем граф и пишем диагностику.
        draft_graph = builder._get_draft_graph()
        ctx.draft_graph = draft_graph
        draft_graph.save(doc.draft_graph_file_path())

        self._log_build_summary(draft_graph)

        # Удаляем неактуальные файлы ручных правок.
        if doc.draft_graph_edits_file_path().exists():
            doc.draft_graph_edits_file_path().unlink()
        if doc.supplementary_facts_ttl_path().exists():
            doc.supplementary_facts_ttl_path().unlink()

        return ModuleResult.ok()

    def _handle_build_exception(
        self,
        ctx: DocumentContext,
        builder: TemplateGraphBuilder,
        ex: Exception,
        normalized_count: int,
        empty_fields: List[str],
    ) -> ModuleResult:
        """
        Обработка исключения внутри code.build(b).
        Сохраняет частичный граф и пишет build_error.json.
        """
        doc = ctx.document
        tctx = ctx.template_ctx
        partial_graph = builder._get_draft_graph()

        # Сохраняем то, что код успел положить, чтобы было что показать в UI.
        try:
            partial_graph.save(doc.draft_graph_file_path())
            ctx.draft_graph = partial_graph
        except Exception:  # noqa: BLE001 — при сохранении тоже могло упасть
            self.log(ERROR, "Не удалось сохранить частично построенный граф", exc_info=True)

        tb_text = traceback.format_exc()

        # Структурированный отчёт.
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "template": {
                "id": tctx.template.id if tctx else None,
                "name": tctx.template.name if tctx else None,
            },
            "exception": {
                "type": type(ex).__name__,
                "message": str(ex),
                "traceback": tb_text.splitlines(),
            },
            "context": {
                "fields_total": len(tctx.fields) if tctx and tctx.fields else 0,
                "fields_normalized": normalized_count,
                "fields_empty": empty_fields,
                "triples_built_before_error": len(partial_graph.triples),
                "incomplete_triples_before_error": sum(
                    1 for t in partial_graph.triples if not t.is_complete()
                ),
            },
            "partial_graph_saved_at": str(doc.draft_graph_file_path().name),
        }

        try:
            doc.build_error_file_path().write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            self.log(ERROR, "Не удалось записать build_error.json", exc_info=True)

        # Лог в основной поток. Сообщение для пользователя — короткое;
        # подробности в build_error.json и draft_graph.json.
        msg = (
            f"Ошибка построения графа: {type(ex).__name__}: {ex}. "
            f"К моменту падения построено {len(partial_graph.triples)} триплет(ов). "
            f"Подробности — в {doc.build_error_file_path().name}."
        )
        self.log(ERROR, msg, exc_info=True)
        return ModuleResult.failed(message=msg)

    def _log_build_summary(self, graph: DraftGraph) -> None:
        """
        Диагностика после успешной сборки.
        Логирует сводку по построенному графу: общая статистика и разбор
        ошибок по полю-источнику.
        """
        total = len(graph.triples)
        complete = sum(1 for t in graph.triples if t.is_complete())
        incomplete = total - complete

        # Распределение по типам триплетов.
        by_type: Counter[str] = Counter(t.triple_type.name for t in graph.triples)
        type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))

        if incomplete == 0:
            self.log(
                INFO,
                f"Сборка завершена: триплетов {total} (все полные); по типам: {type_summary}",
            )
            return

        self.log(
            WARNING,
            f"Сборка завершена с пропусками: триплетов {total} "
            f"(полных {complete}, неполных {incomplete}); по типам: {type_summary}",
        )

        # Сводка ошибок: считаем сколько раз встречается каждое сообщение
        # ошибки и какому полю оно принадлежит. Это самый частый сценарий
        # «не построилось из-за пустого поля» — сразу видно, какое.
        error_by_field: Counter[str] = Counter()
        error_by_message: Counter[str] = Counter()
        for triple in graph.triples:
            for role in ("subject", "predicate", "object"):
                node = triple.get_node(role)
                if node.is_complete() or node.error is None:
                    continue
                source = node.source or "<нет источника>"
                error_by_field[source] += 1
                error_by_message[str(node.error)] += 1

        if error_by_field:
            top_fields = ", ".join(f"{f}={n}" for f, n in error_by_field.most_common(5))
            self.log(WARNING, f"Поля-источники неполных нод (топ-5): {top_fields}")

        if error_by_message:
            for msg, n in error_by_message.most_common(5):
                self.log(WARNING, f"  ×{n}: {msg}")

    @staticmethod
    def _triple_to_repr(triple: DraftTriple) -> Dict[str, Optional[str]]:
        """
        Хелпер на будущее: статистика триплетов.
        Краткое представление триплета для отладочных дампов.
        """
        def short(node) -> Optional[str]:
            d = node._to_json_dict()
            return d.get("n3") or d.get("error")

        return {
            "type": triple.triple_type.name,
            "subject": short(triple.subject),
            "predicate": short(triple.predicate),
            "object": short(triple.object),
        }
