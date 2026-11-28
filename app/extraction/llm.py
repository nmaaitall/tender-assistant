"""Model access. The extractor depends on the LLMClient protocol, not on a provider."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx


class LLMError(RuntimeError):
    """The model call failed or returned something that is not a JSON object."""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


class GroqClient:
    """Groq exposes an OpenAI-compatible chat completions API."""

    url = "https://api.groq.com/openai/v1/chat/completions"
    retry_statuses = {429, 500, 502, 503, 504}

    def __init__(
        self, api_key: str, model: str, timeout: float = 60.0, max_attempts: int = 5
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_attempts = max_attempts

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = self._post(payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(f"Model call failed: {exc}") from exc

        if not isinstance(data, dict):
            raise LLMError("Model did not return a JSON object")
        return data

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """Retries rate limits and server errors, honouring Retry-After when present."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(1, self.max_attempts + 1):
            response = httpx.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            if response.status_code not in self.retry_statuses or attempt == self.max_attempts:
                return response
            time.sleep(_retry_delay(response, attempt))
        return response


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        return min(float(response.headers.get("retry-after", "")), 20.0)
    except ValueError:
        return float(2**attempt)
