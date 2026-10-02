"""Google Gemini client using provider-native JSON-schema structured output."""

from __future__ import annotations

import time

from google import genai
from google.genai import types
from pydantic import BaseModel

from .base import LLMError, LLMResponse


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str, thinking_level: str, timeout_s: float):
        self.model = model
        self._thinking_level = thinking_level
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    def generate_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        if self._thinking_level:
            config.thinking_config = types.ThinkingConfig(thinking_level=self._thinking_level)
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(model=self.model, contents=user, config=config)
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            thinking_tokens=(usage.thoughts_token_count or 0) if usage else 0,
            latency_ms=latency_ms,
            model=response.model_version or self.model,
            token_source="provider_usage_metadata" if usage else "estimated",
        )
