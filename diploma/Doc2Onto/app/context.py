from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING

# Импорты импользуются только локально или для проверки типов,
# чтобы избежать циклических зависимостей
if TYPE_CHECKING:
    import logging
    from infrastructure.storage.document_manager import DocumentManager
    from infrastructure.storage.template_manager import TemplateManager
    from app.pipeline import Pipeline

_app_context: Optional["AppContext"] = None


class AppContext:
    """Контекст приложения, хранящий глобальные сервисы, необходимые во всём проекте."""

    logger: logging.Logger
    doc_manager: DocumentManager
    temp_manager: TemplateManager
    pipeline: Pipeline


def init_app_context() -> AppContext:
    global _app_context
    if _app_context:
        return _app_context

    _app_context = AppContext()

    from app.logger import create_logger
    _app_context.logger = create_logger(False, Path("data/app.log"))
    from infrastructure.storage.document_manager import DocumentManager
    _app_context.doc_manager = DocumentManager(Path("data/documents"))
    from infrastructure.storage.template_manager import TemplateManager
    _app_context.temp_manager = TemplateManager(Path("data/templates"))
    from app.pipeline import Pipeline
    _app_context.pipeline = Pipeline()

    return _app_context


def _ctx() -> AppContext:
    if _app_context is None:
        raise RuntimeError("Контекст приложения не инициализирован. Вызовите init_app_context() перед использованием")
    return _app_context


def _get_context_attr(attr_name: str) -> Any:
    ctx = _ctx()
    if not hasattr(ctx, attr_name):
        raise RuntimeError('Контекст не имеет аттрибута "{attr_name}" или он не инициализирован')
    return getattr(ctx, attr_name)


def get_app_context() -> AppContext:
    return _ctx()


def get_logger() -> logging.Logger:
    return _get_context_attr("logger")


def get_doc_manager() -> DocumentManager:
    return _get_context_attr("doc_manager")


def get_temp_manager() -> TemplateManager:
    return _get_context_attr("temp_manager")


def get_pipeline() -> Pipeline:
    return _get_context_attr("pipeline")
