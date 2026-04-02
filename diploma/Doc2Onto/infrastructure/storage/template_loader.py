import importlib.util
import sys
from typing import Optional

from app.context import get_logger
from core.template.template import Template
from core.template.base import BaseTemplateCode


class TemplateLoader:
    """Динамически загружает код шалона."""

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

            # TODO: сделать дополнительные проверки кода шаблона
            return module.TemplateCode()

        except Exception:
            get_logger().error(f"[TemplateLoader] Error loading template code for {template.name}", exc_info=True)
            return None
