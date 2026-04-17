import os
import logging
from datetime import datetime
from time import perf_counter
from typing import Optional
from openai import DefaultHttpxClient, OpenAI
from pathlib import Path
from string import Template as StringTemplate

from app.settings import DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS, DATA_DIR, LOG_LINE_LENGTH


_client: Optional[OpenAI] = None
_agents_logger: Optional[logging.Logger] = None


def _get_agents_logger() -> logging.Logger:
    """Отдельный логгер для OpenAI-запросов (без общего app logger)."""
    global _agents_logger
    if _agents_logger is not None:
        return _agents_logger

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DATA_DIR / "agents.log"

    logger = logging.getLogger("doc2onto.agents")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _agents_logger = logger
    return logger


def get_openai_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENAI_API_KEY").strip()
    if not api_key:
        raise RuntimeError("Не задана переменная среды OPENAI_API_KEY")

    _client = OpenAI(
        api_key=api_key,
        http_client=DefaultHttpxClient(
            timeout=float(DEFAULT_TIMEOUT_SECONDS),
        ),
    )
    return _client


def ask_gpt(prompt: str, *, system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
    logger = _get_agents_logger()
    used_model = model or DEFAULT_MODEL
    started_at = datetime.now()
    started_perf = perf_counter()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    request_header = [
        "",
        "=" * LOG_LINE_LENGTH,
        f"[OpenAI] {started_at.strftime('%Y-%m-%d %H:%M:%S')} | model={used_model}",
        "-" * LOG_LINE_LENGTH,
        "[SYSTEM PROMPT]",
        system_prompt.strip() if system_prompt else "(none)",
        "-" * LOG_LINE_LENGTH,
        "[USER PROMPT]",
        prompt.strip(),
        "-" * LOG_LINE_LENGTH,
    ]
    logger.info("\n".join(request_header))

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=used_model,
            input=messages,
        )

        text = getattr(response, "output_text", None)
        elapsed_ms = int((perf_counter() - started_perf) * 1000)
        if not text:
            logger.info("\n".join([
                "[ASSISTANT RESPONSE]",
                "(empty)",
                "-" * LOG_LINE_LENGTH,
                f"duration_ms={elapsed_ms}",
                "=" * LOG_LINE_LENGTH,
            ]))
            raise RuntimeError("OpenAI вернул пустой ответ")

        answer = text.strip()
        logger.info("\n".join([
            "[ASSISTANT RESPONSE]",
            answer,
            "-" * LOG_LINE_LENGTH,
            f"duration_ms={elapsed_ms}",
            "=" * LOG_LINE_LENGTH,
        ]))
        return answer

    except Exception as exc:
        elapsed_ms = int((perf_counter() - started_perf) * 1000)
        logger.exception("\n".join([
            "[ERROR]",
            str(exc),
            "-" * LOG_LINE_LENGTH,
            f"duration_ms={elapsed_ms}",
            "=" * LOG_LINE_LENGTH,
        ]))
        raise


def read_prompt(path: Path, **kwargs) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Файл {path} не найден")

    text = path.read_text(encoding="utf-8", errors="strict")
    temp = StringTemplate(text)
    return temp.safe_substitute(**kwargs)
