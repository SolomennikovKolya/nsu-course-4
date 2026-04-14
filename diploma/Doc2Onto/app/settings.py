from pathlib import Path


# Приложение
APP_NAME = "Doc2Onto"
APP_VERSION = "1.0.0"

# Пути хранения файлов и директорий
PROJECT_ROOT = Path(__file__).resolve().parent.parent

META_FILENAME = "meta.json"
DOCUMENTS_BASE_DIR = PROJECT_ROOT / "data" / "documents"
TEMPLATES_BASE_DIR = PROJECT_ROOT / "data" / "templates"
TEMPLATE_CODE_EXAMPLE_PATH = PROJECT_ROOT / "core" / "template" / "code_example.py"
ONTOLOGY_PATH = PROJECT_ROOT / "data" / "ontology.ttl"

ICON_PATH = PROJECT_ROOT / "resources" / "images" / "icon.png"

PROMPTS_BASE_DIR = PROJECT_ROOT / "resources" / "prompts"
GENERATE_DESCR_SYS_PROMPT_PATH = PROMPTS_BASE_DIR / "generate_description_sys.txt"
GENERATE_DESCR_USER_PROMPT_PATH = PROMPTS_BASE_DIR / "generate_description_user.txt"

# OpenAI
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60
