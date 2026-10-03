"""Unit tests for live LLM spend / API-key guards."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import HTTPException

from review_assistant.config import Settings, get_settings
from review_assistant.live_guard import (
    LiveSpendGuard,
    daily_live_spend_usd,
    require_api_key,
    require_api_key_if_configured,
)


def _settings(**overrides) -> Settings:
    base = dict(
        data_dir=Path("."),
        var_dir=Path("."),
        llm_mode="mock",
        gemini_api_key=None,
        gemini_model="gemini-3.1-flash-lite",
        gemini_thinking_level="minimal",
        llm_timeout_s=10.0,
        llm_max_retries=3,
        llm_min_confidence=0.7,
        cache_enabled=True,
        cors_origins=("http://localhost:3417",),
        review_api_key="secret",
        allow_live_batch=False,
        llm_daily_budget_usd=1.0,
        llm_max_concurrent_live=2,
        llm_live_per_minute=5,
        llm_live_per_hour=30,
    )
    base.update(overrides)
    return Settings(**base)


class ApiKeyTests(unittest.TestCase):
    def test_require_api_key_rejects_missing_config(self):
        req = MagicMock()
        req.headers = {}
        with self.assertRaises(HTTPException) as ctx:
            require_api_key(req, _settings(review_api_key=None), purpose="Live LLM reviews")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_api_key_accepts_header(self):
        req = MagicMock()
        req.headers = {"x-api-key": "secret"}
        require_api_key(req, _settings(), purpose="Live LLM reviews")

    def test_require_api_key_accepts_bearer(self):
        req = MagicMock()
        req.headers = {"authorization": "Bearer secret"}
        require_api_key(req, _settings(), purpose="Live LLM reviews")

    def test_require_api_key_rejects_wrong_key(self):
        req = MagicMock()
        req.headers = {"x-api-key": "nope"}
        with self.assertRaises(HTTPException) as ctx:
            require_api_key(req, _settings(), purpose="Live LLM reviews")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_require_if_configured_allows_when_unset(self):
        req = MagicMock()
        req.headers = {}
        require_api_key_if_configured(req, _settings(review_api_key=None))


class SpendGuardTests(unittest.TestCase):
    def test_rate_limit_per_minute(self):
        guard = LiveSpendGuard()
        s = _settings(llm_live_per_minute=2, llm_live_per_hour=100)
        guard.reserve(s, 2)
        with self.assertRaises(HTTPException) as ctx:
            guard.reserve(s, 1)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_concurrency_limit(self):
        guard = LiveSpendGuard()
        s = _settings(llm_max_concurrent_live=1, llm_live_per_minute=100, llm_live_per_hour=100)
        with guard.live_slot(s):
            with self.assertRaises(HTTPException) as ctx:
                with guard.live_slot(s):
                    pass
            self.assertEqual(ctx.exception.status_code, 429)

    def test_daily_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            var = Path(tmp)
            log = var / "logs" / "llm_calls.jsonl"
            log.parent.mkdir(parents=True)
            today = datetime.now(timezone.utc).date().isoformat()
            log.write_text(
                '{"timestamp": "%sT12:00:00+00:00", "provider": "gemini", "cost_usd": 0.9}\n'
                '{"timestamp": "%sT13:00:00+00:00", "provider": "mock", "cost_usd": 0.0}\n'
                % (today, today),
                encoding="utf-8",
            )
            s = _settings(var_dir=var, llm_daily_budget_usd=1.0)
            # Settings.llm_call_log is derived from var_dir via property — rebuild with Path
            # Our _settings uses bare Settings; daily_live_spend uses settings.llm_call_log
            self.assertAlmostEqual(daily_live_spend_usd(s), 0.9)
            guard = LiveSpendGuard()
            s_tight = _settings(var_dir=var, llm_daily_budget_usd=0.5)
            with self.assertRaises(HTTPException) as ctx:
                guard.check_budget(s_tight)
            self.assertEqual(ctx.exception.status_code, 429)


class SettingsEnvTests(unittest.TestCase):
    def tearDown(self):
        get_settings.cache_clear()
        for key in (
            "REVIEW_API_KEY",
            "ALLOW_LIVE_BATCH",
            "LLM_DAILY_BUDGET_USD",
            "LLM_MAX_CONCURRENT_LIVE",
            "LLM_LIVE_PER_MINUTE",
            "LLM_LIVE_PER_HOUR",
        ):
            os.environ.pop(key, None)

    def test_reads_guard_env(self):
        os.environ["REVIEW_API_KEY"] = " from-env "
        os.environ["ALLOW_LIVE_BATCH"] = "true"
        os.environ["LLM_DAILY_BUDGET_USD"] = "2.5"
        os.environ["LLM_MAX_CONCURRENT_LIVE"] = "3"
        os.environ["LLM_LIVE_PER_MINUTE"] = "7"
        os.environ["LLM_LIVE_PER_HOUR"] = "40"
        get_settings.cache_clear()
        s = get_settings()
        self.assertEqual(s.review_api_key, "from-env")
        self.assertTrue(s.allow_live_batch)
        self.assertEqual(s.llm_daily_budget_usd, 2.5)
        self.assertEqual(s.llm_max_concurrent_live, 3)
        self.assertEqual(s.llm_live_per_minute, 7)
        self.assertEqual(s.llm_live_per_hour, 40)


if __name__ == "__main__":
    unittest.main()
