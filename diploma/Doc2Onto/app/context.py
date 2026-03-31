import logging
from pathlib import Path
from typing import Optional

from app.logger import create_logger
from app.pipeline import Pipeline
from infrastructure.storage.document_manager import DocumentManager
from infrastructure.storage.template_manager import TemplateManager


_app_context: Optional["AppContext"] = None


class AppContext:
    """Контекст приложения, хранящий глобальные сервисы, необходимые во всём проекте."""

    def __init__(self):
        self.logger = create_logger(False, Path("data/app.log"))
        self.doc_manager = DocumentManager(Path("data/documents"))
        self.temp_manager = TemplateManager(Path("data/templates"))
        self.pipeline = Pipeline()


def init_app_context() -> AppContext:
    global _app_context
    if _app_context is None:
        _app_context = AppContext()
    return _app_context


def _ctx() -> AppContext:
    if _app_context is None:
        raise RuntimeError("AppContext not initialized")
    return _app_context


def get_app_context() -> AppContext:
    return _ctx()


def get_logger() -> logging.Logger:
    return _ctx().logger


def get_doc_manager() -> DocumentManager:
    return _ctx().doc_manager


def get_temp_manager() -> TemplateManager:
    return _ctx().temp_manager


def get_pipeline() -> Pipeline:
    return _ctx().pipeline
