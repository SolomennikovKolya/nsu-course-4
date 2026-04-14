import os
from typing import Optional
from openai import DefaultHttpxClient, OpenAI
from pathlib import Path
from string import Template as StringTemplate

from app.settings import DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS

_client: Optional[OpenAI] = None


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
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    client = get_openai_client()
    response = client.responses.create(
        model=model or DEFAULT_MODEL,
        input=messages,
    )

    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("OpenAI вернул пустой ответ")

    return text.strip()


def read_prompt(path: Path, **kwargs) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Файл {path} не найден")

    text = path.read_text(encoding="utf-8", errors="strict")
    temp = StringTemplate(text)
    return temp.safe_substitute(**kwargs)
