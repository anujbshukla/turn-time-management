from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings


class SemanticProvider(ABC):
    @abstractmethod
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError


class GeminiProvider(SemanticProvider):
    """Hosted Gemini provider using only the Python standard library."""

    def __init__(self) -> None:
        settings = get_settings()

        self.api_key = (
            settings.gemini_api_key or ""
        ).strip()

        self.model = (
            settings.copilot_nl_model
            or "gemini-3.5-flash-lite"
        ).strip()

        self.base_url = (
            settings.copilot_nl_base_url
            or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")

        self.timeout = float(
            settings.copilot_nl_timeout_seconds
        )

        self.max_retries = int(
            settings.copilot_nl_max_retries
        )

        self.retry_base_seconds = float(
            settings.copilot_nl_retry_base_seconds
        )

        self.retry_max_seconds = float(
            settings.copilot_nl_retry_max_seconds
        )

        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required when "
                "COPILOT_NL_PROVIDER=gemini"
            )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/models/"
            f"{self.model}:generateContent"
        )

        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_prompt,
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_prompt,
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0,
            },
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        payload: dict[str, Any] | None = None
        last_error: Exception | None = None

        for attempt in range(
            self.max_retries + 1
        ):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

                break

            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )[:1000]

                retryable = (
                    exc.code == 429
                    or 500 <= exc.code <= 599
                )

                if not retryable:
                    raise RuntimeError(
                        "Gemini API request failed "
                        f"({exc.code}): {detail}"
                    ) from exc

                last_error = exc

                if attempt >= self.max_retries:
                    raise RuntimeError(
                        "Gemini API request failed after "
                        f"{attempt + 1} attempts "
                        f"({exc.code}): {detail}"
                    ) from exc

            except (
                TimeoutError,
                urllib.error.URLError,
            ) as exc:
                last_error = exc

                if attempt >= self.max_retries:
                    raise RuntimeError(
                        "Gemini API request failed after "
                        f"{attempt + 1} attempts: {exc}"
                    ) from exc

            delay = min(
                self.retry_base_seconds
                * (2 ** attempt),
                self.retry_max_seconds,
            )

            delay += random.uniform(
                0,
                min(
                    1.0,
                    delay * 0.1,
                ),
            )

            print(
                "Gemini request attempt "
                f"{attempt + 1} failed; "
                f"retrying in {delay:.1f}s..."
            )

            time.sleep(delay)

        if payload is None:
            raise RuntimeError(
                "Gemini API request failed: "
                f"{last_error}"
            )

        try:
            text = (
                payload["candidates"][0]
                ["content"]
                ["parts"][0]
                ["text"]
            )

            return json.loads(text)

        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "Gemini returned an invalid "
                "structured response"
            ) from exc


class OpenAIProvider(SemanticProvider):
    def __init__(self) -> None:
        settings = get_settings()

        self.model = (
            settings.copilot_nl_model
            or "gpt-5-mini"
        ).strip()

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI

        except ImportError as exc:
            raise RuntimeError(
                "Install the OpenAI SDK with: "
                "pip install openai"
            ) from exc

        response = OpenAI().responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name":
                        "warehouse_canonical_query",
                    "schema": schema,
                    "strict": True,
                }
            },
        )

        return json.loads(
            response.output_text
        )


class OllamaProvider(SemanticProvider):
    def __init__(self) -> None:
        settings = get_settings()

        self.model = (
            settings.copilot_nl_model
            or "qwen2.5:7b-instruct"
        ).strip()

        self.base_url = (
            settings.copilot_nl_base_url
            or "http://localhost:11434"
        ).rstrip("/")

        self.timeout = float(
            settings.copilot_nl_timeout_seconds
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": 0,
            },
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(
                body
            ).encode("utf-8"),
            headers={
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            return json.loads(
                payload["message"]["content"]
            )

        except (
            urllib.error.URLError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "Ollama structured request "
                f"failed: {exc}"
            ) from exc


def build_semantic_provider() -> SemanticProvider:
    settings = get_settings()

    provider = (
        settings.copilot_nl_provider
        or "gemini"
    ).strip().lower()

    if provider == "gemini":
        return GeminiProvider()

    if provider == "openai":
        return OpenAIProvider()

    if provider == "ollama":
        return OllamaProvider()

    raise RuntimeError(
        "Unsupported COPILOT_NL_PROVIDER="
        f"{provider!r}. "
        "Supported providers: "
        "gemini, openai, ollama."
    )