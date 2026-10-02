from __future__ import annotations

from ..config import Settings
from .base import LLMClient
from .mock import MockClient


def get_llm_client(settings: Settings, requested_mode: str | None = None) -> tuple[LLMClient, str]:
    """Return (client, mode). Live is used only when requested and a key is configured."""
    mode = (requested_mode or settings.effective_llm_mode).lower()
    if mode == "live" and settings.gemini_configured:
        from .gemini import GeminiClient

        return (
            GeminiClient(
                api_key=settings.gemini_api_key or "",
                model=settings.gemini_model,
                thinking_level=settings.gemini_thinking_level,
                timeout_s=settings.llm_timeout_s,
            ),
            "live",
        )
    return MockClient(), "mock"
