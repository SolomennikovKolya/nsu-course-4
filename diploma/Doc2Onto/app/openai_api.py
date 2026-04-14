from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal
from urllib import error, request


OpenAIModel = Literal["gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"]
SUPPORTED_MODELS: tuple[OpenAIModel, ...] = ("gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano")
DEFAULT_MODEL: OpenAIModel = "gpt-5.4-mini"


class OpenAIAPIError(RuntimeError):
    """Ошибка при обращении к OpenAI API."""


@dataclass(slots=True)
class OpenAIProxyClient:
    """
    Минимальный клиент для генерации ответа по промпту через OpenAI Responses API.

    Все HTTPS-запросы отправляются через прокси, если передан `proxy_url`.
    """

    api_key: str
    proxy_url: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: int = 60

    def generate(
        self,
        prompt: str,
        *,
        model: OpenAIModel = DEFAULT_MODEL,
        system_prompt: str | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Генерирует текстовый ответ модели по пользовательскому промпту."""
        self._validate_model(model)

        if not self.api_key.strip():
            raise ValueError("api_key не должен быть пустым")
        if not prompt.strip():
            raise ValueError("prompt не должен быть пустым")

        payload: dict[str, Any] = {"model": model}
        if system_prompt:
            payload["input"] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        else:
            payload["input"] = prompt
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens

        req = request.Request(
            url=f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        opener = self._build_opener()
        try:
            with opener.open(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OpenAIAPIError(f"HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise OpenAIAPIError(f"Ошибка сети/прокси: {exc.reason}") from exc

        data = json.loads(raw)
        text = self._extract_text(data)
        if text is None:
            raise OpenAIAPIError("Не удалось извлечь текст из ответа OpenAI API")
        return text

    def _build_opener(self) -> request.OpenerDirector:
        if self.proxy_url:
            handler = request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
            return request.build_opener(handler)
        return request.build_opener()

    @staticmethod
    def _validate_model(model: str) -> None:
        if model not in SUPPORTED_MODELS:
            allowed = ", ".join(SUPPORTED_MODELS)
            raise ValueError(f"Неподдерживаемая модель '{model}'. Доступно: {allowed}")

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str | None:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = data.get("output")
        if not isinstance(output, list):
            return None

        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "output_text":
                    text = entry.get("text")
                    if isinstance(text, str):
                        chunks.append(text)

        result = "".join(chunks).strip()
        return result or None
