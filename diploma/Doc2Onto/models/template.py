"""DTO шаблонов обработки документов, а также контекст шаблона для оптимальной работы с тяжеловесными данными."""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.context import get_logger
from core.fields.field import Field
from core.template.base import BaseTemplateCode


@dataclass
class Template:
    """Представляет информацию о шаблоне обработки документов."""

    id: str  # Уникальный идентификатор (имя каталога хранения)
    directory: Path  # Директория, где хранятся данные шаблона
    name: str  # Отображаемое название / класс документа
    description: str | None = None  # Описание шаблона

    def code_file_path(self):
        return self.directory / "code.py"


class TemplateContext:
    """
    Контекст шаблона, предоставляющий доступ к тяжеловесным данным.
    Используется для оптимальной работы с шаблонами в рамках пайплайна.

    Принцип работы:
    - При первом обращении к данным, они загружаются из соответствующего файла.
    - При последующих обращениях к данным, они берутся из кеша.
    - Данные можно перезаписать путём обычным присваиванием.
    - Данные можно удалить путём вызова метода unload().
    """

    def __init__(self, temp: Template):
        self.template: Template = temp
        self._code: BaseTemplateCode | None = None
        self._fields: list[Field] | None = None

    @property
    def code(self) -> BaseTemplateCode | None:
        if self._code is not None:
            return self._code
        try:
            self._code = TemplateCodeLoader.load(self.template)
            return self._code
        except Exception:
            return None

    @code.setter
    def code(self, code: BaseTemplateCode | None):
        self._code = code

    @property
    def fields(self) -> list[Field] | None:
        if self._fields is not None:
            return self._fields
        try:
            code = self.code
            if code is None:
                return None

            self._fields = code.fields()
            return self._fields
        except Exception:
            return None

    @fields.setter
    def fields(self, fields: list[Field] | None):
        self._fields = fields

    def unload(self):
        self._code = None
        self._fields = None


@contextmanager
def template_context(temp: Template):
    ctx = TemplateContext(temp)
    try:
        yield ctx
    finally:
        ctx.unload()


class TemplateCodeLoader:
    """Динамический загрузчик кода шаблона."""

    @staticmethod
    def validate(code: BaseTemplateCode):
        """Статическая проверка экземпляра кода шаблона."""
        try:
            cls = type(code)
            abstract = getattr(cls, "__abstractmethods__", None)
            if abstract:
                names = ", ".join(sorted(abstract))
                raise ValueError(f"Класс TemplateCode остаётся абстрактным, не реализованы: {names}.")

            for name in ("classify", "fields", "build"):
                if not callable(getattr(code, name, None)):
                    raise ValueError(f"Метод «{name}» отсутствует или не является вызываемым.")

        except Exception:
            get_logger().error("[TemplateCodeLoader] Error validating template code", exc_info=True)
            raise

    @staticmethod
    def load(template: Template) -> BaseTemplateCode:
        """Загружает код шаблона из файла."""
        try:
            code_path = template.code_file_path()
            if not code_path.exists():
                raise FileNotFoundError("Code file not found for template")

            module_name = f"template_{template.id.replace('-', '_')}"

            spec = importlib.util.spec_from_file_location(module_name, code_path)
            if spec is None or spec.loader is None:
                raise ValueError("Invalid spec for template")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "TemplateCode"):
                raise ValueError("TemplateCode class not found in code module")

            return module.TemplateCode()

        except Exception:
            get_logger().error(
                f"[TemplateCodeLoader] Error loading template code for {template.name}", exc_info=True
            )
            raise
