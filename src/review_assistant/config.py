"""Runtime configuration, read from environment variables (and an optional, gitignored .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)

RULE_SET_VERSION = "rules-2026.10.1"
PROMPT_VERSION = "sop03-diagnosis-v1"

# USD per 1M tokens, Gemini Developer API "Standard" tier.
# Source: https://ai.google.dev/gemini-api/docs/pricing (accessed 2026-10-02).
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75},
}
PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
PRICING_ACCESS_DATE = "2026-10-02"


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    var_dir: Path
    llm_mode: str
    gemini_api_key: str | None
    gemini_model: str
    gemini_thinking_level: str
    llm_timeout_s: float
    llm_max_retries: int
    llm_min_confidence: float
    cache_enabled: bool
    cors_origins: tuple[str, ...]
    review_api_key: str | None
    allow_live_batch: bool
    llm_daily_budget_usd: float
    llm_max_concurrent_live: int
    llm_live_per_minute: int
    llm_live_per_hour: int

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def review_api_key_configured(self) -> bool:
        return bool(self.review_api_key)

    @property
    def effective_llm_mode(self) -> str:
        """`live` only if requested and a key is present; otherwise the mock is used."""
        return "live" if self.llm_mode == "live" and self.gemini_configured else "mock"

    @property
    def logs_dir(self) -> Path:
        return self.var_dir / "logs"

    @property
    def llm_call_log(self) -> Path:
        return self.logs_dir / "llm_calls.jsonl"

    @property
    def audit_log(self) -> Path:
        return self.logs_dir / "audit.jsonl"

    @property
    def app_log(self) -> Path:
        return self.logs_dir / "app.log"

    @property
    def cache_dir(self) -> Path:
        return self.var_dir / "cache" / "llm"

    @property
    def reviews_dir(self) -> Path:
        return self.var_dir / "reviews"


def _optional_secret(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")),
        var_dir=Path(os.getenv("VAR_DIR", PROJECT_ROOT / "var")),
        llm_mode=os.getenv("LLM_MODE", "live").strip().lower(),
        gemini_api_key=_optional_secret("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        gemini_thinking_level=os.getenv("GEMINI_THINKING_LEVEL", "minimal"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "10")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        llm_min_confidence=float(os.getenv("LLM_MIN_CONFIDENCE", "0.7")),
        cache_enabled=_bool("LLM_CACHE_ENABLED", True),
        cors_origins=tuple(
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:3417,http://127.0.0.1:3417"
            ).split(",")
            if o.strip()
        ),
        review_api_key=_optional_secret("REVIEW_API_KEY"),
        allow_live_batch=_bool("ALLOW_LIVE_BATCH", False),
        llm_daily_budget_usd=float(os.getenv("LLM_DAILY_BUDGET_USD", "1.0")),
        llm_max_concurrent_live=int(os.getenv("LLM_MAX_CONCURRENT_LIVE", "2")),
        llm_live_per_minute=int(os.getenv("LLM_LIVE_PER_MINUTE", "5")),
        llm_live_per_hour=int(os.getenv("LLM_LIVE_PER_HOUR", "30")),
    )
