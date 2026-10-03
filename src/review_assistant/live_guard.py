"""Guards against unauthenticated and unbounded live LLM spend over HTTP."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from fastapi import HTTPException, Request

from .config import Settings
from .llm.calllog import read_jsonl


def extract_api_key(request: Request) -> str | None:
    header = request.headers.get("x-api-key")
    if header and header.strip():
        return header.strip()
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    return None


def _keys_match(provided: str, expected: str) -> bool:
    """Constant-time compare via hashes so unequal lengths do not raise."""
    return secrets.compare_digest(
        hashlib.sha256(provided.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


def require_api_key(request: Request, settings: Settings, *, purpose: str) -> None:
    """Require a configured REVIEW_API_KEY and a matching request credential."""
    expected = settings.review_api_key
    if not expected:
        raise HTTPException(
            status_code=403,
            detail=f"{purpose} requires REVIEW_API_KEY to be configured on the server.",
        )
    provided = extract_api_key(request)
    if not provided or not _keys_match(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Pass X-API-Key or Authorization: Bearer.",
        )


def require_api_key_if_configured(request: Request, settings: Settings) -> None:
    """When REVIEW_API_KEY is set, require it; otherwise allow (local mock browsing)."""
    if not settings.review_api_key:
        return
    provided = extract_api_key(request)
    if not provided or not _keys_match(provided, settings.review_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Pass X-API-Key or Authorization: Bearer.",
        )


def resolve_llm_mode(requested: str | None, settings: Settings) -> str:
    if requested is not None:
        return requested
    return settings.effective_llm_mode


def daily_live_spend_usd(settings: Settings) -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    spent = 0.0
    for row in read_jsonl(settings.llm_call_log):
        ts = str(row.get("timestamp") or "")
        if not ts.startswith(today):
            continue
        if row.get("provider") == "mock":
            continue
        spent += float(row.get("cost_usd") or 0.0)
    return round(spent, 6)


class LiveSpendGuard:
    """In-process concurrency, rate, and daily budget limits for live Gemini calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timestamps: deque[float] = deque()
        self._inflight = 0

    def reset(self) -> None:
        """Test helper."""
        with self._lock:
            self._timestamps.clear()
            self._inflight = 0

    def check_budget(self, settings: Settings) -> None:
        budget = settings.llm_daily_budget_usd
        if budget <= 0:
            return
        spent = daily_live_spend_usd(settings)
        if spent >= budget:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily live LLM budget of ${budget:.2f} USD exhausted "
                    f"(spent ${spent:.4f})."
                ),
            )

    def _prune(self, now: float) -> None:
        cutoff = now - 3600.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def reserve(self, settings: Settings, n: int = 1) -> None:
        """Reserve n live-review slots against per-minute / per-hour limits and budget."""
        if n < 1:
            return
        self.check_budget(settings)
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            minute_ago = now - 60.0
            recent_min = sum(1 for t in self._timestamps if t >= minute_ago)
            if recent_min + n > settings.llm_live_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail="Live LLM rate limit exceeded (per minute). Retry later.",
                )
            if len(self._timestamps) + n > settings.llm_live_per_hour:
                raise HTTPException(
                    status_code=429,
                    detail="Live LLM rate limit exceeded (per hour). Retry later.",
                )
            for _ in range(n):
                self._timestamps.append(now)

    def _acquire_concurrency(self, settings: Settings) -> None:
        with self._lock:
            if self._inflight >= settings.llm_max_concurrent_live:
                raise HTTPException(
                    status_code=429,
                    detail="Too many concurrent live LLM reviews. Retry later.",
                )
            self._inflight += 1

    def _release_concurrency(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    @contextmanager
    def live_slot(self, settings: Settings, *, reserved: bool = False) -> Iterator[None]:
        """Acquire budget/rate (unless already reserved) and a concurrency slot."""
        if not reserved:
            self.reserve(settings, 1)
        self._acquire_concurrency(settings)
        try:
            yield
        finally:
            self._release_concurrency()


live_spend_guard = LiveSpendGuard()
