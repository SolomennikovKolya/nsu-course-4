import os
from openai import DefaultHttpxClient, OpenAI

from app.settings import DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENAI_API_KEY").strip()
    if not api_key:
        raise RuntimeError("Не задана переменная среды OPENAI_API_KEY")
    # proxy_url = os.getenv("OPENAI_PROXY_URL").strip()
    # if not proxy_url:
    #     raise RuntimeError("Не задана переменная среды OPENAI_PROXY_URL")

    _client = OpenAI(
        api_key=api_key,
        http_client=DefaultHttpxClient(
            # proxy=proxy_url,
            timeout=float(DEFAULT_TIMEOUT_SECONDS),
        ),
    )
    return _client


def ask_openai(prompt: str, *, system_prompt: str | None = None, model: str | None = None) -> str:
    used_model = model or DEFAULT_MODEL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = get_openai_client().responses.create(
        model=used_model,
        input=messages,
    )
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()
    raise RuntimeError("OpenAI вернул пустой ответ")
