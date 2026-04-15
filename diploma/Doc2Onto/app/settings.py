from pathlib import Path


# Приложение
APP_NAME = "Doc2Onto"
APP_VERSION = "1.0.0"

# Директории и пути хранения файлов
PROJECT_ROOT = Path(__file__).resolve().parent.parent

META_FILENAME = "meta.json"
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_BASE_DIR = DATA_DIR / "documents"
TEMPLATES_BASE_DIR = DATA_DIR / "templates"
ONTOLOGY_PATH = DATA_DIR / "ontology.ttl"

TEMPLATE_CODE_EXAMPLE_PATH = PROJECT_ROOT / "core" / "template" / "code_example.py"

PROMPTS_DIR = PROJECT_ROOT / "resources" / "prompts"
GENERATE_DESCR_SYS_PROMPT_PATH = PROMPTS_DIR / "generate_description_sys.txt"
GENERATE_DESCR_USER_PROMPT_PATH = PROMPTS_DIR / "generate_description_user.txt"
GENERATE_TEMP_SYS_PROMPT_PATH = PROMPTS_DIR / "generate_template_code_sys.txt"
GENERATE_TEMP_USER_PROMPT_PATH = PROMPTS_DIR / "generate_template_code_user.txt"
EXTRACT_FIELDS_SYS_PROMPT_PATH = PROMPTS_DIR / "extract_fields_sys.txt"
EXTRACT_FIELDS_USER_PROMPT_PATH = PROMPTS_DIR / "extract_fields_user.txt"

ICON_PATH = PROJECT_ROOT / "resources" / "images" / "icon.png"

# Настройки OpenAI
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60
