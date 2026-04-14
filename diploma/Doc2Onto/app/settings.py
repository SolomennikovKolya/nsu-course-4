from pathlib import Path


# Пути хранения файлов и директорий
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_BASE_DIR = PROJECT_ROOT / "data" / "documents"
TEMPLATES_BASE_DIR = PROJECT_ROOT / "data" / "templates"
TEMPLATE_CODE_EXAMPLE_PATH = PROJECT_ROOT / "core" / "template" / "code_example.py"
META_FILENAME = "meta.json"
ONTOLOGY_PATH = PROJECT_ROOT / "data" / "ontology.ttl"

# OpenAI
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60
