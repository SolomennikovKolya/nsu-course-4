import importlib.util
import sys
from typing import Optional

from app.context import get_logger
from core.template.base import BaseTemplateCode
from core.template.template import Template


class TemplateLoader:
    """Динамически загружает код шаблона."""

    @staticmethod
    def validate_code(code: BaseTemplateCode):
        """
        Статическая проверка экземпляра кода шаблона.

        Проверяется отсутствие нереализованных абстрактных методов и наличие ожидаемых методов.
        """

        cls = type(code)
        abstract = getattr(cls, "__abstractmethods__", None)
        if abstract:
            names = ", ".join(sorted(abstract))
            raise ValueError(f"Класс TemplateCode остаётся абстрактным, не реализованы: {names}.")

        for name in ("classify", "fields", "validate", "build_triples"):
            if not callable(getattr(code, name, None)):
                raise ValueError(f"Метод «{name}» отсутствует или не является вызываемым.")

    @staticmethod
    def load(template: Template) -> Optional[BaseTemplateCode]:
        try:
            code_path = template.code_file_path()
            if not code_path.exists():
                return None

            module_name = f"template_{template.name.replace(' ', '_')}"

            spec = importlib.util.spec_from_file_location(module_name, code_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "TemplateCode"):
                return None

            return module.TemplateCode()

        except Exception:
            get_logger().error(f"[TemplateLoader] Error loading template code for {template.name}", exc_info=True)
            return None
