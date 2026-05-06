"""
Структурированная валидация кода шаблона.

Проверки разделены на пять категорий:

* ``structure``  — экземпляр действительно реализует ``BaseTemplateCode``
  (не абстрактный, все три метода вызываемы).
* ``security``   — AST-анализ ``code.py``: запрет на опасные импорты
  (``os``, ``subprocess``, ``socket``, …) и обращения к ``open()`` /
  ``exec()`` / ``eval()`` / ``__import__`` / ``__subclasses__``.
* ``fields``     — динамический вызов ``code.fields()``: возвращён список,
  все элементы — ``Field`` с непустыми ``name`` / ``description`` / тремя
  DSL-объектами, имена в snake_case без дубликатов.
* ``classify``   — динамический вызов ``code.classify("test", UDDM([]))``,
  проверка возвращаемого типа ``bool``.
* ``build``      — динамический сухой прогон ``code.build(builder)`` с фиктивными
  значениями всех объявленных полей; ловит ошибки трансформеров и логики.
* ``ontology``   — сверка обращений ``ONTO.<имя>`` / ``ONTO[<имя>]`` из
  ``code.py`` с локальными именами схемы (классы и свойства из ``schema.ttl``).

Каждое замечание представляется :class:`ValidationIssue` с уровнем ``error`` /
``warning``. Конечный отчёт — :class:`TemplateValidationReport` — годен и для
программной проверки (``has_errors``), и для отображения в UI.
"""
from __future__ import annotations

import ast
import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set

from rdflib import Graph, OWL, RDF, URIRef
from rdflib.namespace import RDFS

from app.settings import ONTOLOGY_SCHEMA_PATH, SUBJECT_NAMESPACE_IRI
from core.fields.field import Field
from core.fields.field_extractor import FieldExtractor
from core.fields.field_selector import FieldSelector
from core.fields.field_validator import FieldValidator
from core.graph.template_graph_builder import TemplateGraphBuilder
from core.template.base import BaseTemplateCode
from core.uddm.model import UDDM


# Разрешённые root-имена модулей для импорта в коде шаблона.
# Сюда входят все необходимые проектные пакеты и безопасные стандартные модули.
_ALLOWED_IMPORT_ROOTS: Set[str] = {
    # Внутренние пакеты проекта — без них шаблон не работает
    "core",
    "app",
    "models",
    "modules",
    "storage",
    # Безопасные стандартные модули (чисто вычислительные)
    "re",
    "datetime",
    "typing",
    "dataclasses",
    "enum",
    "json",
    "math",
    "collections",
    "itertools",
    "functools",
    "string",
    "abc",
    "decimal",
    "fractions",
    "statistics",
    "uuid",
    "hashlib",
    "secrets",
    "unicodedata",
    "html",
    "textwrap",
    # Безопасные сторонние библиотеки, уже использующиеся в проекте
    "rdflib",
    "pymorphy3",
}

# Запрещённые root-имена. Перечисление ведётся с понятным сообщением об угрозе.
_FORBIDDEN_IMPORT_ROOTS: dict[str, str] = {
    "os": "доступ к файловой системе и переменным окружения",
    "sys": "доступ к интерпретатору и параметрам процесса",
    "subprocess": "запуск внешних процессов",
    "socket": "сетевые соединения",
    "http": "сетевые соединения",
    "urllib": "сетевые соединения",
    "requests": "сетевые соединения",
    "ftplib": "сетевые соединения",
    "smtplib": "сетевые соединения",
    "telnetlib": "сетевые соединения",
    "shutil": "массовые операции с файловой системой",
    "tempfile": "запись на диск",
    "pathlib": "доступ к файловой системе",
    "ctypes": "вызов нативного кода",
    "multiprocessing": "запуск процессов",
    "threading": "потоки",
    "asyncio": "асинхронный ввод/вывод",
    "pickle": "десериализация произвольных объектов",
    "marshal": "десериализация произвольных объектов",
    "shelve": "запись на диск",
    "dbm": "запись на диск",
    "fcntl": "низкоуровневые операции с файлами",
    "signal": "управление сигналами процесса",
    "importlib": "динамическая загрузка модулей",
    "builtins": "переопределение встроенных функций",
}

# Запрещённые встроенные функции (вызовы как функций — open(), exec(), eval(), …)
_FORBIDDEN_BUILTIN_CALLS: dict[str, str] = {
    "open": "запись/чтение файлов",
    "exec": "выполнение произвольного кода",
    "eval": "выполнение произвольных выражений",
    "compile": "компиляция произвольного кода",
    "__import__": "динамический импорт",
    "input": "ожидание ввода блокирует пайплайн",
    "breakpoint": "интерактивный отладчик блокирует пайплайн",
}

# Запрещённые «магические» атрибуты, через которые можно сломать sandbox.
_FORBIDDEN_ATTRIBUTES: Set[str] = {
    "__subclasses__",
    "__globals__",
    "__getattribute__",
    "__class__",  # запрещаем .__class__.__bases__[...].__subclasses__()
    "__bases__",
    "__import__",
    "__builtins__",
    "__loader__",
    "__spec__",
}

# Имя поля шаблона: snake_case, начинается с буквы.
_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# ---------------------------------------------------------------------------
# Структуры результата
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """Одно замечание валидации шаблона."""

    severity: str        # "error" | "warning"
    category: str        # structure | security | fields | classify | build | ontology
    message: str
    detail: Optional[str] = None  # длинный текст: traceback или контекст

    def is_error(self) -> bool:
        return self.severity == "error"

    def is_warning(self) -> bool:
        return self.severity == "warning"


@dataclass
class TemplateValidationReport:
    """Итог валидации: набор замечаний + удобные предикаты для UI."""

    issues: List[ValidationIssue] = field(default_factory=list)

    # ----- предикаты -----

    @property
    def has_errors(self) -> bool:
        return any(i.is_error() for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.is_warning() for i in self.issues)

    @property
    def is_valid(self) -> bool:
        return not self.has_errors

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.is_error()]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.is_warning()]

    # ----- мутаторы -----

    def add_error(self, category: str, message: str, detail: Optional[str] = None) -> None:
        self.issues.append(ValidationIssue("error", category, message, detail))

    def add_warning(self, category: str, message: str, detail: Optional[str] = None) -> None:
        self.issues.append(ValidationIssue("warning", category, message, detail))

    def extend(self, other: "TemplateValidationReport") -> None:
        self.issues.extend(other.issues)

    # ----- сериализация для логов -----

    def summary(self) -> str:
        if not self.issues:
            return "Шаблон валиден: замечаний нет."
        parts = [f"{len(self.errors)} ошибка(и), {len(self.warnings)} предупреждение(й)."]
        for it in self.issues:
            tag = "ERR" if it.is_error() else "WARN"
            parts.append(f"  [{tag}/{it.category}] {it.message}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Главная точка входа
# ---------------------------------------------------------------------------


def validate_template_code(
    code: Optional[BaseTemplateCode],
    *,
    code_path: Optional[Path] = None,
    schema_path: Optional[Path] = None,
) -> TemplateValidationReport:
    """
    Полностью проверяет код шаблона и возвращает структурированный отчёт.

    Args:
        code: Загруженный экземпляр TemplateCode (может быть None — если загрузка
            упала ещё на импорте; тогда статически проверяется только AST/безопасность).
        code_path: Путь к ``code.py`` для AST-проверок. Если не задан — секции
            ``security`` и ``ontology`` пропускаются.
        schema_path: Путь к ``schema.ttl``. По умолчанию используется
            :data:`ONTOLOGY_SCHEMA_PATH`.

    Returns:
        Заполненный :class:`TemplateValidationReport` со всеми замечаниями.
    """
    report = TemplateValidationReport()

    # 1. Структура
    fields_list = _validate_structure(code, report)

    # 2. Безопасность (AST)
    code_tree: Optional[ast.AST] = None
    if code_path is not None and code_path.exists():
        code_tree = _load_ast(code_path, report)
        if code_tree is not None:
            _validate_security(code_tree, report)
    elif code_path is not None:
        report.add_warning(
            "security",
            f"Файл кода шаблона не найден: {code_path}; проверка безопасности пропущена.",
        )

    if code is None:
        # Нет смысла дальше что-либо динамически вызывать — отчёт всё равно даст
        # критическую ошибку структуры.
        return report

    # 3. Классификатор
    _validate_classify(code, report)

    # 4. Поля
    if fields_list is not None:
        _validate_fields_list(fields_list, report)

        # 5. Сухой прогон build()
        _validate_build(code, fields_list, report)

    # 6. Сверка с онтологией
    if code_tree is not None:
        schema = schema_path or ONTOLOGY_SCHEMA_PATH
        if schema.exists():
            _validate_ontology(code_tree, schema, report)
        else:
            report.add_warning(
                "ontology",
                f"Файл онтологии {schema} не найден; сверка имён пропущена.",
            )

    return report


# ---------------------------------------------------------------------------
# 1. Структура
# ---------------------------------------------------------------------------


def _validate_structure(
    code: Optional[BaseTemplateCode],
    report: TemplateValidationReport,
) -> Optional[List[Field]]:
    """Базовые статические проверки. Возвращает список полей, если он успел
    загрузиться (для последующих секций)."""
    if code is None:
        report.add_error(
            "structure",
            "Код шаблона не удалось загрузить (ошибка импорта code.py).",
            detail="Скорее всего класс TemplateCode отсутствует или модуль падает при импорте.",
        )
        return None

    cls = type(code)
    abstract = getattr(cls, "__abstractmethods__", None)
    if abstract:
        names = ", ".join(sorted(abstract))
        report.add_error(
            "structure",
            f"Класс TemplateCode остаётся абстрактным; не реализованы: {names}.",
        )

    for name in ("classify", "fields", "build"):
        method = getattr(code, name, None)
        if not callable(method):
            report.add_error(
                "structure",
                f"Метод «{name}» отсутствует или не является вызываемым.",
            )

    # Попытка вызвать fields() здесь даёт нам данные сразу для других секций.
    fields_method = getattr(code, "fields", None)
    if not callable(fields_method):
        return None
    try:
        result = fields_method()
    except Exception as ex:
        report.add_error(
            "fields",
            f"Метод fields() выбросил исключение: {ex}",
            detail=traceback.format_exc(),
        )
        return None

    if not isinstance(result, list):
        report.add_error(
            "fields",
            f"Метод fields() должен возвращать List[Field], получено {type(result).__name__}.",
        )
        return None

    return result


# ---------------------------------------------------------------------------
# 2. Безопасность
# ---------------------------------------------------------------------------


def _load_ast(code_path: Path, report: TemplateValidationReport) -> Optional[ast.AST]:
    try:
        source = code_path.read_text(encoding="utf-8")
    except OSError as ex:
        report.add_error("security", f"Не удалось прочитать code.py: {ex}")
        return None
    try:
        return ast.parse(source, filename=str(code_path))
    except SyntaxError as ex:
        report.add_error(
            "security",
            f"Синтаксическая ошибка в code.py: {ex.msg} (line {ex.lineno})",
            detail=str(ex),
        )
        return None


def _validate_security(tree: ast.AST, report: TemplateValidationReport) -> None:
    """AST-проверки безопасности — без выполнения кода."""
    for node in ast.walk(tree):

        # ---------- import / from ... import ... ----------
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import_root(alias.name, node, report)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            _check_import_root(module_name, node, report)

        # ---------- вызов запрещённого builtin (open / exec / eval / …) ----------
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_BUILTIN_CALLS:
                threat = _FORBIDDEN_BUILTIN_CALLS[func.id]
                report.add_warning(
                    "security",
                    f"Использование `{func.id}()` запрещено в коде шаблона ({threat}).",
                    detail=_position_detail(node),
                )

        # ---------- доступ к опасному атрибуту ----------
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRIBUTES:
                report.add_warning(
                    "security",
                    f"Обращение к `.{node.attr}` запрещено в коде шаблона "
                    f"(потенциальный обход sandbox).",
                    detail=_position_detail(node),
                )


def _check_import_root(module_name: str, node: ast.AST, report: TemplateValidationReport) -> None:
    if not module_name:
        return
    root = module_name.split(".", 1)[0]
    if root in _FORBIDDEN_IMPORT_ROOTS:
        threat = _FORBIDDEN_IMPORT_ROOTS[root]
        report.add_warning(
            "security",
            f"Импорт `{module_name}` запрещён в коде шаблона ({threat}).",
            detail=_position_detail(node),
        )
        return
    if root not in _ALLOWED_IMPORT_ROOTS:
        # Не помечаем как ошибку: вдруг пользователь имеет легитимную либу.
        # Но фиксируем для внимания.
        report.add_warning(
            "security",
            f"Неизвестный модуль `{module_name}` в коде шаблона. "
            f"Если это легитимная зависимость — добавьте её в список разрешённых.",
            detail=_position_detail(node),
        )


def _position_detail(node: ast.AST) -> str:
    line = getattr(node, "lineno", None)
    col = getattr(node, "col_offset", None)
    if line is None:
        return ""
    return f"строка {line}, колонка {col}"


# ---------------------------------------------------------------------------
# 3. Поля
# ---------------------------------------------------------------------------


def _validate_fields_list(fields_list: List[Field], report: TemplateValidationReport) -> None:
    if not fields_list:
        report.add_error("fields", "Метод fields() вернул пустой список — нечего извлекать.")
        return

    seen_names: Set[str] = set()
    for idx, f in enumerate(fields_list):
        prefix = f"fields()[{idx}]"
        if not isinstance(f, Field):
            report.add_error(
                "fields",
                f"{prefix}: ожидается экземпляр Field, получен {type(f).__name__}.",
            )
            continue

        if not isinstance(f.name, str) or not f.name.strip():
            report.add_error("fields", f"{prefix}: поле без имени (`name` пустое).")
        elif not _FIELD_NAME_RE.match(f.name):
            report.add_warning(
                "fields",
                f"Имя поля `{f.name}` не соответствует snake_case [a-z][a-z0-9_]*; "
                f"в IRI и JSON-payload это даст плохо читаемые ключи.",
            )
        else:
            if f.name in seen_names:
                report.add_error("fields", f"Дубликат имени поля: `{f.name}`.")
            seen_names.add(f.name)

        if not isinstance(f.description, str) or not f.description.strip():
            report.add_warning(
                "fields",
                f"Поле `{f.name}` не имеет содержательного описания. "
                f"Описание используется для LLM-извлечения и LLM-валидации; без него качество извлечения упадёт.",
            )

        if not isinstance(f.selector, FieldSelector):
            report.add_error("fields", f"Поле `{f.name}`: selector должен быть FieldSelector.")
        if not isinstance(f.extractor, FieldExtractor):
            report.add_error("fields", f"Поле `{f.name}`: extractor должен быть FieldExtractor.")
        if not isinstance(f.validator, FieldValidator):
            report.add_error("fields", f"Поле `{f.name}`: validator должен быть FieldValidator.")


# ---------------------------------------------------------------------------
# 4. Классификатор
# ---------------------------------------------------------------------------


def _validate_classify(code: BaseTemplateCode, report: TemplateValidationReport) -> None:
    classify = getattr(code, "classify", None)
    if not callable(classify):
        # Уже зафиксировано в structure.
        return
    try:
        result = classify("__test_doc__", UDDM([]))
    except Exception as ex:
        report.add_error(
            "classify",
            f"Метод classify() упал на тестовом вызове: {ex}",
            detail=traceback.format_exc(),
        )
        return

    if not isinstance(result, bool):
        report.add_warning(
            "classify",
            f"classify() вернул {type(result).__name__}, ожидается bool. "
            f"Сравнение в пайплайне может быть некорректным.",
        )


# ---------------------------------------------------------------------------
# 5. Сухой прогон build()
# ---------------------------------------------------------------------------


def _validate_build(
    code: BaseTemplateCode,
    fields_list: List[Field],
    report: TemplateValidationReport,
) -> None:
    """Проверяет, что build() не падает на синтетических значениях полей.

    Значения подбираются такими, чтобы пройти типовые трансформеры (ФИО, дата,
    группа, направление, организация). Если поле всё-таки не парсится — это
    нестрашно: build() обычно трактует ошибки трансформера как «неполный IRI»
    и не падает, а помечает узел.
    """
    dummy_values = {f.name: _synth_value(f.name) for f in fields_list if isinstance(f, Field)}

    # Подсунем «фиктивные» значения, не зависящие от реальных шаблонов.
    builder = TemplateGraphBuilder(dummy_values)
    try:
        code.build(builder)
    except Exception as ex:
        report.add_error(
            "build",
            f"Метод build() упал на сухом прогоне с фиктивными значениями: {ex}",
            detail=traceback.format_exc(),
        )


# Подбирается на основе подсказок в имени поля: имя содержит «фио» → используем
# заведомо парсящееся ФИО, «дат» → ISO-дата и т. п. Иначе — нейтральная строка.
_NAME_HINTS: List[tuple[str, str]] = [
    ("фио", "Иванов Иван Иванович"),
    ("name", "Иванов Иван Иванович"),
    ("student", "Иванов Иван Иванович"),
    ("supervisor", "Петров Пётр Петрович"),
    ("scientist", "Сидоров Сидор Сидорович"),
    ("дата", "2024-09-01"),
    ("date", "2024-09-01"),
    ("год", "2024-2025"),
    ("year", "2024-2025"),
    ("группа", "22204"),
    ("group", "22204"),
    ("направлен", "09.03.04"),
    ("direction", "09.03.04"),
    ("профил", "Программная инженерия"),
    ("profile", "Программная инженерия"),
    ("тема", "Тестовая тема"),
    ("topic", "Тестовая тема"),
    ("title", "Тестовая тема"),
    ("организац", "Новосибирский государственный университет"),
    ("organization", "Новосибирский государственный университет"),
    ("кафедр", "Кафедра общей информатики"),
    ("department", "Кафедра общей информатики"),
    ("должн", "доцент"),
    ("position", "доцент"),
    ("степен", "к.ф.-м.н."),
    ("degree", "к.ф.-м.н."),
    ("звани", "доцент"),
    ("title_acad", "доцент"),
    ("вид_практик", "учебная практика"),
    ("practice_kind", "учебная практика"),
    ("оценк", "отлично"),
    ("grade", "отлично"),
    ("email", "test@example.org"),
    ("phone", "+79991234567"),
    ("телефон", "+79991234567"),
]


def _synth_value(name: str) -> str:
    lower = (name or "").lower()
    for hint, value in _NAME_HINTS:
        if hint in lower:
            return value
    return "Тестовое значение"


# ---------------------------------------------------------------------------
# 6. Сверка с онтологией
# ---------------------------------------------------------------------------


def _validate_ontology(
    tree: ast.AST,
    schema_path: Path,
    report: TemplateValidationReport,
) -> None:
    """Сверяет все имена ``ONTO.<x>`` / ``ONTO[<x>]`` в коде со схемой."""
    try:
        g = Graph()
        g.parse(schema_path, format="turtle")
    except Exception as ex:
        report.add_warning(
            "ontology",
            f"Не удалось распарсить онтологию ({schema_path}): {ex}; сверка имён пропущена.",
        )
        return

    schema_locals = _collect_schema_locals(g)
    used_names = _collect_onto_references(tree)

    for ref_name, lineno in sorted(used_names):
        if ref_name in schema_locals:
            continue
        # Близкие имена — может быть опечатка.
        suggestion = _closest_match(ref_name, schema_locals)
        msg = f"`ONTO.{ref_name}` не найдено в онтологии."
        if suggestion:
            msg += f" Возможно, имелось в виду `ONTO.{suggestion}`?"
        detail = f"строка {lineno}" if lineno else None
        report.add_warning("ontology", msg, detail=detail)


def _collect_schema_locals(g: Graph) -> Set[str]:
    """Все local-name из нашей онтологии: классы, свойства, индивиды перечислений."""
    out: Set[str] = set()
    for typ in (
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.NamedIndividual,
        RDFS.Class,
        RDF.Property,
    ):
        for s in g.subjects(RDF.type, typ):
            if isinstance(s, URIRef) and str(s).startswith(SUBJECT_NAMESPACE_IRI):
                local = str(s)[len(SUBJECT_NAMESPACE_IRI):]
                if local:
                    out.add(local)
    return out


def _collect_onto_references(tree: ast.AST) -> Iterable[tuple[str, Optional[int]]]:
    """Ищет в AST обращения к глобальному имени ``ONTO``: ``ONTO.<x>`` и ``ONTO[<x>]``.

    Возвращает пары ``(имя, номер_строки)``.
    """
    found: List[tuple[str, Optional[int]]] = []
    for node in ast.walk(tree):
        # ONTO.<name>
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "ONTO":
            found.append((node.attr, getattr(node, "lineno", None)))
            continue
        # ONTO[<name>]  — где <name> это строковая константа
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "ONTO":
            slice_node = node.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                found.append((slice_node.value, getattr(node, "lineno", None)))
    return found


def _closest_match(name: str, candidates: Set[str]) -> Optional[str]:
    """Быстрый помощник для подсказок: ищет имя, отличающееся 1–2 символами."""
    if not candidates:
        return None
    lower = name.lower()
    best: Optional[str] = None
    best_score = 999
    for c in candidates:
        if c.lower() == lower:
            return c
        # Дешёвый score: длина симметричной разницы по символам.
        score = abs(len(c) - len(name)) + len(set(c.lower()) ^ set(lower))
        if score < best_score:
            best_score = score
            best = c
    if best_score <= 4:
        return best
    return None
