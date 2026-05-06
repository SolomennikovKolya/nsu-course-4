from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pymorphy3


ValueTransformResult = Dict[str, Optional[str]]
ValueTransformFunc = Callable[[str], ValueTransformResult]


_ORG_PREFIXES_RE = re.compile(
    r"^(?:фгбоу\s+во|фгбуну?|фгуп|фгуп\s+нии|фгбун|фгаоу\s+во|оаo|оао|зао|пао|ао|ооо|тоо)\s+",
    re.IGNORECASE,
)

_RU_MONTHS: Dict[str, int] = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


# ---------------------------------------------------------------------------
# Морфологический анализатор для приведения частей ФИО в именительный падеж.
# В документах часто встречается родительный/винительный/дательный падеж
# и без морфологии хеш ФИО получается разным для одного и того же человека.
# ---------------------------------------------------------------------------

_morph = pymorphy3.MorphAnalyzer()

_PART_TAG: Dict[str, str] = {
    "surname": "Surn",
    "first": "Name",
    "patronymic": "Patr",
}


def _detect_gender(first_name: str) -> Optional[str]:
    """Определяет пол ('masc'/'femn'/None) по имени через pymorphy."""
    if not first_name:
        return None
    cleaned = first_name.strip()
    if len(cleaned.replace(".", "")) <= 2:
        return None
    for parsed in _morph.parse(cleaned):
        if "Name" in parsed.tag:
            tag = parsed.tag
            if "masc" in tag:
                return "masc"
            if "femn" in tag:
                return "femn"
    return None


def _to_nominative(word: str, *, kind: str, gender: Optional[str] = None) -> str:
    """Приводит часть ФИО (фамилию/имя/отчество) к именительному падежу.

    Стратегия:
      * слово в 1–2 символа (инициал) и пустые — оставляем как есть;
      * фамилии через дефис нормализуем покомпонентно;
      * берём только разборы pymorphy с подходящим тегом части ФИО (Surn / Name / Patr).
        Если таких нет — любая «коррекция» опасна (например, «Соломенников» pymorphy
        читает как мн. ч. от «соломенник» и без тега Surn даст «Соломенники»),
        поэтому возвращаем слово без изменений;
      * среди типизированных разборов предпочитаем тот, чей пол (`masc`/`femn`) совпадает
        с полом, известным извне (определённым по имени). Это снимает омонимию
        «Соломенникова Николая» (мужской gent) ↔ «Соломенникова Мария» (женский nomn);
      * затем sing > plur и nomn > не-nomn; в противном случае делаем `inflect({'nomn'})`.
    """
    if not word:
        return word

    cleaned = word.strip()
    if not cleaned:
        return word

    if "-" in cleaned and not cleaned.endswith("-"):
        return "-".join(_to_nominative(p, kind=kind, gender=gender) for p in cleaned.split("-"))

    if len(cleaned.replace(".", "")) <= 2:
        return cleaned

    target_tag = _PART_TAG.get(kind)
    if target_tag is None:
        return cleaned

    parses = _morph.parse(cleaned)
    typed = [p for p in parses if target_tag in p.tag]
    if not typed:
        return cleaned

    def _gender_score(p) -> int:
        if gender is None:
            return 0
        if gender in p.tag:
            return 0
        # обратный пол — последняя надежда
        return 2 if (("masc" in p.tag) or ("femn" in p.tag)) else 1

    typed.sort(
        key=lambda p: (
            _gender_score(p),
            0 if "sing" in p.tag else 1,
            0 if "nomn" in p.tag else 1,
        )
    )

    for parsed in typed:
        if "nomn" in parsed.tag:
            return _restore_case(cleaned, parsed.word)
        inflected = parsed.inflect({"nomn"})
        if inflected is not None and inflected.word:
            return _restore_case(cleaned, inflected.word)

    return cleaned


def _restore_case(original: str, normalized: str) -> str:
    """Сохраняет регистр первой буквы исходного слова."""
    if not original or not normalized:
        return normalized
    if original[0].isupper():
        return normalized[:1].upper() + normalized[1:]
    return normalized


# ---------------------------------------------------------------------------
# Таблицы синонимов для перечислений онтологии
# ---------------------------------------------------------------------------

# (синоним, local_name индивида онтологии). Порядок важен:
# более длинные/специфичные ключи стоят раньше более коротких.

_POSITION_SYNONYMS: List[Tuple[str, str]] = [
    ("заведующий кафедрой", "Должность_ЗаведующийКафедрой"),
    ("зав. кафедрой", "Должность_ЗаведующийКафедрой"),
    ("зав кафедрой", "Должность_ЗаведующийКафедрой"),
    ("директор института", "Должность_ДиректорИнститута"),
    ("декан", "Должность_Декан"),
    ("ректор", "Должность_Ректор"),
    ("главный научный сотрудник", "Должность_ГлавныйНаучныйСотрудник"),
    ("ведущий научный сотрудник", "Должность_ВедущийНаучныйСотрудник"),
    ("в.н.с.", "Должность_ВедущийНаучныйСотрудник"),
    ("внс", "Должность_ВедущийНаучныйСотрудник"),
    ("старший научный сотрудник", "Должность_СтаршийНаучныйСотрудник"),
    ("с.н.с.", "Должность_СтаршийНаучныйСотрудник"),
    ("снс", "Должность_СтаршийНаучныйСотрудник"),
    ("младший научный сотрудник", "Должность_МладшийНаучныйСотрудник"),
    ("научный сотрудник", "Должность_НаучныйСотрудник"),
    ("старший преподаватель", "Должность_СтаршийПреподаватель"),
    ("преподаватель", "Должность_Преподаватель"),
    ("ассистент", "Должность_Ассистент"),
    ("профессор", "Должность_Профессор"),
    ("доцент", "Должность_Доцент"),
    ("лаборант", "Должность_Лаборант"),
    ("секретарь", "Должность_Секретарь"),
]

_DEGREE_SYNONYMS: List[Tuple[str, str]] = [
    ("кандидат физико-математических наук", "УченаяСтепень_КандидатФизМатНаук"),
    ("к.ф.-м.н.", "УченаяСтепень_КандидатФизМатНаук"),
    ("кфмн", "УченаяСтепень_КандидатФизМатНаук"),
    ("доктор физико-математических наук", "УченаяСтепень_ДокторФизМатНаук"),
    ("д.ф.-м.н.", "УченаяСтепень_ДокторФизМатНаук"),
    ("дфмн", "УченаяСтепень_ДокторФизМатНаук"),
    ("кандидат технических наук", "УченаяСтепень_КандидатТехнНаук"),
    ("к.т.н.", "УченаяСтепень_КандидатТехнНаук"),
    ("ктн", "УченаяСтепень_КандидатТехнНаук"),
    ("доктор технических наук", "УченаяСтепень_ДокторТехнНаук"),
    ("д.т.н.", "УченаяСтепень_ДокторТехнНаук"),
    ("дтн", "УченаяСтепень_ДокторТехнНаук"),
    ("кандидат педагогических наук", "УченаяСтепень_КандидатПедНаук"),
    ("к.п.н.", "УченаяСтепень_КандидатПедНаук"),
    ("доктор педагогических наук", "УченаяСтепень_ДокторПедНаук"),
    ("д.п.н.", "УченаяСтепень_ДокторПедНаук"),
]

_TITLE_SYNONYMS: List[Tuple[str, str]] = [
    ("член-корреспондент ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("чл.-корр. ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("чл-корр ран", "УченоеЗвание_ЧленКорреспондентРАН"),
    ("академик ран", "УченоеЗвание_АкадемикРАН"),
    ("академик риа", "УченоеЗвание_АкадемикРИА"),
    ("профессор", "УченоеЗвание_Профессор"),
    ("доцент", "УченоеЗвание_Доцент"),
]

_PRACTICE_KIND_SYNONYMS: List[Tuple[str, str]] = [
    ("научно-исследовательская работа", "ВидПрактики_НИР"),
    ("нир", "ВидПрактики_НИР"),
    ("преддипломная практика", "ВидПрактики_Преддипломная"),
    ("преддипломная", "ВидПрактики_Преддипломная"),
    ("эксплуатационная практика", "ВидПрактики_Эксплуатационная"),
    ("эксплуатационная", "ВидПрактики_Эксплуатационная"),
    ("производственная практика", "ВидПрактики_Производственная"),
    ("производственная", "ВидПрактики_Производственная"),
    ("учебная практика", "ВидПрактики_Учебная"),
    ("учебная", "ВидПрактики_Учебная"),
]

_GRADE_SYNONYMS: List[Tuple[str, str]] = [
    ("отлично", "Оценка_Отлично"),
    ("хорошо", "Оценка_Хорошо"),
    ("удовлетворительно", "Оценка_Удовлетворительно"),
    ("неудовлетворительно", "Оценка_Неудовлетворительно"),
    ("неуд", "Оценка_Неудовлетворительно"),
    ("отл", "Оценка_Отлично"),
    ("хор", "Оценка_Хорошо"),
    ("удовл", "Оценка_Удовлетворительно"),
    ("5", "Оценка_Отлично"),
    ("4", "Оценка_Хорошо"),
    ("3", "Оценка_Удовлетворительно"),
    ("2", "Оценка_Неудовлетворительно"),
]


def _match_enum(value: str, table: Iterable[Tuple[str, str]]) -> Optional[str]:
    """Подстрочный матч значения против таблицы синонимов (case-insensitive, ё→е)."""
    if not value:
        return None
    text = value.strip().lower().replace("ё", "е")
    if not text:
        return None
    for needle, local in table:
        if needle in text:
            return local
    return None


# ---------------------------------------------------------------------------
# Основной класс
# ---------------------------------------------------------------------------


class ValueTransformer:
    """
    Утилиты нормализации значений и построения детерминированных IRI-хешей.
    Все хеши — sha1, первые 12 символов.

    Используются и в шаблонах (b.field(...).transform(ValueTransformer.X, key="hash")),
    и в высокоуровневых хелперах TemplateGraphBuilder, и в Reconciler-е.
    """

    HASH_LEN = 12

    @staticmethod
    def person(value: str) -> ValueTransformResult:
        """
        Нормализует ФИО: морфологическое приведение к именительному падежу + хеш.

        Шаги:
          1. Чистка пробелов, замена 'ё'→'е', разбиение на токены по пробелам и точкам.
          2. Каждая часть (фамилия/имя/отчество) приводится к именительному падежу
             через pymorphy3 (кроме инициалов длиной ≤ 2). Это обеспечивает, что
             «Соломенниковой Николае Александровиче» (предложный падеж) и
             «Соломенников Николай Александрович» (именительный) дают один и тот же IRI.
          3. Каноническая форма: ``lower(нормализованная_фамилия)|первая_буква_имени|первая_буква_отчества``.

        Возвращает словарь:
          - ``last_name`` — нормализованная фамилия в именительном (с восстановлением регистра).
          - ``first_name`` — нормализованное имя (или инициал) в именительном.
          - ``middle_name`` — нормализованное отчество в именительном (None, если нет).
          - ``name`` — полное ФИО в именительном падеже (готово для литерала :фио).
          - ``canonical`` — каноническая форма (для отладки/Reconciler).
          - ``hash`` — IRI-локальное имя ``Персона_<sha1[:12]>``.
        """
        cleaned = ValueTransformer._clean_text(value)
        parts = [p for p in re.split(r"[\s.]+", cleaned) if p]
        if len(parts) < 2:
            raise ValueError(
                f"ФИО должно содержать как минимум фамилию и имя/инициал: {value!r}"
            )

        last_raw = parts[0]
        first_raw = parts[1]
        middle_raw = parts[2] if len(parts) > 2 else None

        gender = _detect_gender(first_raw) or (
            _detect_gender(middle_raw) if middle_raw else None
        )

        last_norm = _to_nominative(last_raw, kind="surname", gender=gender)
        first_norm = _to_nominative(first_raw, kind="first", gender=gender)
        middle_norm = (
            _to_nominative(middle_raw, kind="patronymic", gender=gender)
            if middle_raw
            else None
        )

        last_canon = ValueTransformer._normalize_word(last_norm)
        first_initial = ValueTransformer._first_letter(first_norm)
        middle_initial = ValueTransformer._first_letter(middle_norm) if middle_norm else ""

        if not last_canon or not first_initial:
            raise ValueError(f"Не удалось извлечь фамилию и инициал имени: {value!r}")

        canonical = f"{last_canon}|{first_initial}|{middle_initial}"
        h = "Персона_" + ValueTransformer._hash(canonical)

        full_parts = [last_norm, first_norm]
        if middle_norm:
            full_parts.append(middle_norm)
        full_name = " ".join(full_parts)

        return {
            "last_name": last_norm,
            "first_name": first_norm,
            "middle_name": middle_norm,
            "name": full_name,
            "canonical": canonical,
            "hash": h,
        }

    @staticmethod
    def organization(value: str) -> ValueTransformResult:
        """
        Нормализует наименование организации:
          - lowercase, удаление кавычек, схлопывание пробелов и тире,
          - удаление частых юридических префиксов ('ФГБОУ ВО', 'ФГБУН' и т. п.).
        """
        if not value or not value.strip():
            raise ValueError("Пустое название организации")

        text = ValueTransformer._clean_text(value)
        text = text.lower().replace("\u00a0", " ")
        text = re.sub(r"[«»\"']+", "", text)
        text = re.sub(r"[\u2010-\u2015]", "-", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = _ORG_PREFIXES_RE.sub("", text).strip()

        if not text:
            raise ValueError(f"После нормализации название организации пустое: {value!r}")

        return {
            "name": value.strip(),
            "canonical": text,
            "hash": "Организация_" + ValueTransformer._hash(text),
        }

    @staticmethod
    def profile(value: str) -> ValueTransformResult:
        """Нормализует название профиля (lowercase, схлопывание пробелов)."""
        if not value or not value.strip():
            raise ValueError("Пустое название профиля")

        text = ValueTransformer._clean_text(value).lower()
        text = re.sub(r"\s+", " ", text).strip()
        return {
            "name": value.strip(),
            "canonical": text,
            "hash": "Профиль_" + ValueTransformer._hash(text),
        }

    @staticmethod
    def thesis(value: str) -> ValueTransformResult:
        """Нормализует тему ВКР (lowercase, удаление кавычек, лишних пробелов и пунктуации)."""
        if not value or not value.strip():
            raise ValueError("Пустая тема ВКР")

        text = ValueTransformer._clean_text(value).lower()
        text = re.sub(r"[«»\"']+", "", text)
        text = re.sub(r"[\u2010-\u2015]", "-", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*[.!?]+\s*$", "", text)

        return {
            "title": value.strip(),
            "canonical": text,
            "hash": "ВКР_" + ValueTransformer._hash(text),
        }

    @staticmethod
    def practice(value: Dict[str, str] | str) -> ValueTransformResult:
        """
        IRI Практики — хеш от тройки (person_iri, practice_kind, academic_year).

        Принимает либо dict с обязательными ключами person/kind/year, либо строку
        формата 'person|kind|year' (для совместимости с шаблоном).
        """
        if isinstance(value, dict):
            person = (value.get("person") or "").strip()
            kind = (value.get("kind") or "").strip()
            year = (value.get("year") or "").strip()
        else:
            parts = (value or "").split("|")
            if len(parts) != 3:
                raise ValueError(
                    "ValueTransformer.practice: ожидался dict {person, kind, year} или строка 'person|kind|year'"
                )
            person, kind, year = (p.strip() for p in parts)

        if not person or not kind or not year:
            raise ValueError("ValueTransformer.practice: person/kind/year не должны быть пустыми")

        canonical = f"{person.lower()}|{kind.lower()}|{year.lower()}"
        return {
            "canonical": canonical,
            "hash": "Практика_" + ValueTransformer._hash(canonical),
        }

    @staticmethod
    def group(value: str) -> ValueTransformResult:
        """
        Номер группы → стабильный local-name :Группа_<номер>.

        Извлекает первое подходящее обозначение группы из строки. Поддерживает:
          * чисто числовые номера ('22204', '22204а'),
          * буквенно-цифровые ('М-2024-1', 'А-12').
        Числовая часть длиной ≥ 3 имеет приоритет — это отсекает шум вроде
        слова «группы» или «№» в исходной строке.
        """
        if not value or not value.strip():
            raise ValueError("Пустой номер группы")

        s = ValueTransformer._clean_text(value)
        m = re.search(r"\d{3,}[A-Za-zА-Яа-я]*", s)
        if m is None:
            m = re.search(r"[A-Za-zА-Яа-я]+[-_]?\d+", s)
        if m is None:
            m = re.search(r"\d+", s)
        if m is None:
            raise ValueError(f"Не удалось разобрать номер группы: {value!r}")
        token = m.group(0)
        return {
            "number": token,
            "local": "Группа_" + token,
        }

    @staticmethod
    def direction(value: str) -> ValueTransformResult:
        """
        Код направления подготовки (формат XX.XX.XX) → :Направление_XX_XX_XX.

        Если в строке встречается код в каноническом формате — берётся он.
        Иначе строка-нормализация: только цифры и точки/подчёркивания.
        """
        if not value or not value.strip():
            raise ValueError("Пустой код направления подготовки")

        s = ValueTransformer._clean_text(value)
        m = re.search(r"\d{2}\.\d{2}\.\d{2}", s)
        if not m:
            raise ValueError(f"Не удалось извлечь код направления вида XX.XX.XX: {value!r}")
        code = m.group(0)
        return {
            "code": code,
            "local": "Направление_" + code.replace(".", "_"),
        }

    @staticmethod
    def position(value: str) -> ValueTransformResult:
        """Должность (свободный текст) → именованный индивид перечисления :Должность."""
        local = _match_enum(value, _POSITION_SYNONYMS)
        if not local:
            raise ValueError(f"Не удалось сопоставить должность с :Должность: {value!r}")
        return {"name": value.strip(), "local": local}

    @staticmethod
    def degree(value: str) -> ValueTransformResult:
        """Учёная степень (свободный текст) → :УченаяСтепень_X."""
        local = _match_enum(value, _DEGREE_SYNONYMS)
        if not local:
            raise ValueError(f"Не удалось сопоставить учёную степень: {value!r}")
        return {"name": value.strip(), "local": local}

    @staticmethod
    def title(value: str) -> ValueTransformResult:
        """Учёное звание (свободный текст) → :УченоеЗвание_X."""
        local = _match_enum(value, _TITLE_SYNONYMS)
        if not local:
            raise ValueError(f"Не удалось сопоставить учёное звание: {value!r}")
        return {"name": value.strip(), "local": local}

    @staticmethod
    def practice_kind(value: str) -> ValueTransformResult:
        """Вид практики (свободный текст) → :ВидПрактики_X."""
        local = _match_enum(value, _PRACTICE_KIND_SYNONYMS)
        if not local:
            raise ValueError(f"Не удалось сопоставить вид практики: {value!r}")
        return {"name": value.strip(), "local": local}

    @staticmethod
    def grade(value: str) -> ValueTransformResult:
        """Итоговая оценка (свободный текст или число) → :Оценка_X."""
        local = _match_enum(value, _GRADE_SYNONYMS)
        if not local:
            raise ValueError(f"Не удалось сопоставить оценку: {value!r}")
        return {"name": value.strip(), "local": local}

    @staticmethod
    def email(value: str) -> ValueTransformResult:
        parts = (value or "").split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Email должен содержать ровно одну '@' и непустые части")
        local, domain = parts
        canonical = (local + "@" + domain).strip().lower()
        return {
            "local": local,
            "domain": domain,
            "email": canonical,
            "hash": "Email_" + ValueTransformer._hash(canonical),
        }

    @staticmethod
    def date(value: str) -> ValueTransformResult:
        """
        Парсит русские форматы дат:
          '20 декабря 2024 г.', '12.09.2025', '29.09.25',
          '"29" сентября 2025 г.', '«29» сентября 2025 г.'
        Возвращает {iso, year, month, day, hash}.
        """
        if not value or not value.strip():
            raise ValueError("Пустая строка даты")

        s = ValueTransformer._clean_text(value).strip()
        s = s.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
        s = re.sub(r"\s+г\.?\s*$", "", s).strip()

        m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                dt = datetime(y, mo, d).date()
                return ValueTransformer._date_result(dt)
            except ValueError as ex:
                raise ValueError(f"Некорректная дата: {value!r}") from ex

        m = re.search(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})", s)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                dt = datetime(y, mo, d).date()
                return ValueTransformer._date_result(dt)
            except ValueError as ex:
                raise ValueError(f"Некорректная дата: {value!r}") from ex

        m = re.search(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})", s)
        if m:
            d = int(m.group(1))
            month_word = m.group(2).lower()
            y = int(m.group(3))
            for prefix, mo in _RU_MONTHS.items():
                if month_word.startswith(prefix):
                    try:
                        dt = datetime(y, mo, d).date()
                        return ValueTransformer._date_result(dt)
                    except ValueError as ex:
                        raise ValueError(f"Некорректная дата: {value!r}") from ex

        raise ValueError(f"Не удалось распарсить дату: {value!r}")

    @staticmethod
    def telephone(value: str) -> ValueTransformResult:
        """Нормализация в +7XXXXXXXXXX. Принимает '+7 ...', '8 ...', '7 ...' и любой мусор."""
        if not value:
            raise ValueError("Пустой номер телефона")
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith(("7", "8")):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError(f"Не удалось нормализовать номер: {value!r}")
        canonical = "+7" + digits
        return {
            "telephone": canonical,
            "canonical": canonical,
            "hash": "Телефон_" + ValueTransformer._hash(canonical),
        }

    # ---------- helpers ----------

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[: ValueTransformer.HASH_LEN]

    @staticmethod
    def _clean_text(value: str) -> str:
        if value is None:
            return ""
        text = str(value)
        text = text.replace("ё", "е").replace("Ё", "Е")
        text = text.replace("\u00a0", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_word(word: str) -> str:
        return ValueTransformer._clean_text(word).lower().replace(".", "")

    @staticmethod
    def _first_letter(word: Optional[str]) -> str:
        if not word:
            return ""
        n = ValueTransformer._normalize_word(word)
        return n[0] if n else ""

    @staticmethod
    def _date_result(dt) -> ValueTransformResult:
        iso = dt.isoformat()
        return {
            "iso": iso,
            "year": str(dt.year),
            "month": f"{dt.month:02d}",
            "day": f"{dt.day:02d}",
            "hash": "Дата_" + ValueTransformer._hash(iso),
        }
