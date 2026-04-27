from pathlib import Path


# --- приложение ---
APP_NAME = "Doc2Onto"
APP_VERSION = "1.0.0"

# --- настройки агентов ---
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60

# --- онтология ---
SUBJECT_NAMESPACE_IRI = "http://doc2onto.org/ontology#"

# --- GUI и логи ---
LOG_ALIGN_WIDTH = 30
LOG_LINE_LENGTH = 96

# --- файловая структура ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent

META_FILENAME = "meta.json"
TEMPLATE_CODE_EXAMPLE_PATH = PROJECT_ROOT / "resources" / "template" / "code_example.py"

DATA_DIR = PROJECT_ROOT / ".data"
DOCUMENTS_DIR = DATA_DIR / "documents"
TEMPLATES_DIR = DATA_DIR / "templates"
ONTOLOGY_DIR = DATA_DIR / "ontology"
LOG_DIR = DATA_DIR / "logs"

APP_LOG_PATH = LOG_DIR / "app.log"
AGENTS_LOG_PATH = LOG_DIR / "agents.log"
ONTOLOGY_PATH = DATA_DIR / "ontology.ttl"

PROMPTS_DIR = PROJECT_ROOT / "resources" / "prompts"
GENERATE_DESCR_SYS_PROMPT_PATH = PROMPTS_DIR / "generate_description_sys.txt"
GENERATE_DESCR_USER_PROMPT_PATH = PROMPTS_DIR / "generate_description_user.txt"
GENERATE_TEMP_SYS_PROMPT_PATH = PROMPTS_DIR / "generate_template_code_sys.txt"
GENERATE_TEMP_USER_PROMPT_PATH = PROMPTS_DIR / "generate_template_code_user.txt"
EXTRACT_FIELDS_SYS_PROMPT_PATH = PROMPTS_DIR / "extract_fields_sys.txt"
EXTRACT_FIELDS_USER_PROMPT_PATH = PROMPTS_DIR / "extract_fields_user.txt"
VALIDATE_FIELDS_SYS_PROMPT_PATH = PROMPTS_DIR / "validate_fields_sys.txt"
VALIDATE_FIELDS_USER_PROMPT_PATH = PROMPTS_DIR / "validate_fields_user.txt"

ICON_PATH = PROJECT_ROOT / "resources" / "images" / "icon.png"
