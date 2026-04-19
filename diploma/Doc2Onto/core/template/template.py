from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import importlib.util
import sys
from typing import Optional

from app.context import get_logger
from core.template.base import BaseTemplateCode
from core.template.field import Field


@dataclass
class Template:
    """Представляет информацию о шаблоне обработки документов."""

    name: str                          # Название шаблона (класс документа)
    directory: Path                    # Директория, где хранятся данные шаблона
    description: Optional[str] = None  # Описание шаблона

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
        self._code: Optional[BaseTemplateCode] = None
        self._fields: Optional[List[Field]] = None

    @property
    def code(self) -> Optional[BaseTemplateCode]:
        if self._code is not None:
            return self._code
        try:
            self._code = TemplateCodeLoader.load(self.template)
            return self._code
        except Exception as exc:
            # raise RuntimeError(f"Failed to load code into template context: {exc}") from exc
            return None

    @code.setter
    def code(self, code: Optional[BaseTemplateCode]):
        self._code = code

    @property
    def fields(self) -> Optional[List[Field]]:
        if self._fields is not None:
            return self._fields
        try:
            self._fields = self.code.fields()
            return self._fields
        except Exception as exc:
            # raise RuntimeError(f"Failed to load fields into template context: {exc}") from exc
            return None

    @fields.setter
    def fields(self, fields: Optional[List[Field]]):
        self._fields = fields

    def unload(self):
        self._code = None
        self._fields = None


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

            for name in ("classify", "fields", "build_triples"):
                if not callable(getattr(code, name, None)):
                    raise ValueError(f"Метод «{name}» отсутствует или не является вызываемым.")

        except Exception as exc:
            get_logger().error(f"[TemplateCodeLoader] Error validating template code", exc_info=True)
            raise

    @staticmethod
    def load(template: Template) -> Optional[BaseTemplateCode]:
        """Загружает код шаблона из файла."""
        try:
            code_path = template.code_file_path()
            if not code_path.exists():
                raise FileNotFoundError(f"Code file not found for template")

            module_name = f"template_{template.name.replace(' ', '_')}"

            spec = importlib.util.spec_from_file_location(module_name, code_path)
            if spec is None or spec.loader is None:
                raise ValueError(f"Invalid spec for template")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "TemplateCode"):
                raise ValueError(f"TemplateCode class not found in code module")

            return module.TemplateCode()

        except Exception as exc:
            get_logger().error(f"[TemplateCodeLoader] Error loading template code for {template.name}", exc_info=True)
            raise
