"""Provider-neutral LLM interface. Live and mock clients return the same shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    latency_ms: int
    model: str
    token_source: str  # "provider_usage_metadata" | "estimated"


class LLMError(RuntimeError):
    """Raised when the provider fails after transport-level retries."""


class LLMClient(Protocol):
    provider: str
    model: str

    def generate_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResponse: ...
