"""HTTP-level tests for cost/DoS gates on review endpoints."""

from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from review_assistant.config import get_settings
from review_assistant.live_guard import live_spend_guard


class ApiGuardTests(unittest.TestCase):
    def setUp(self):
        live_spend_guard.reset()
        get_settings.cache_clear()
        # Isolate from the developer's .env for these assertions.
        os.environ["LLM_MODE"] = "mock"
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("REVIEW_API_KEY", None)
        os.environ["ALLOW_LIVE_BATCH"] = "false"
        os.environ["LLM_LIVE_PER_MINUTE"] = "5"
        os.environ["LLM_LIVE_PER_HOUR"] = "30"
        get_settings.cache_clear()
        from review_assistant.api import app

        self.client = TestClient(app)

    def tearDown(self):
        live_spend_guard.reset()
        get_settings.cache_clear()
        for key in (
            "LLM_MODE",
            "GEMINI_API_KEY",
            "REVIEW_API_KEY",
            "ALLOW_LIVE_BATCH",
            "LLM_LIVE_PER_MINUTE",
            "LLM_LIVE_PER_HOUR",
        ):
            os.environ.pop(key, None)

    def test_health_exposes_guard_flags(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("review_api_key_configured", body)
        self.assertIn("allow_live_batch", body)
        self.assertFalse(body["review_api_key_configured"])

    def test_mock_review_allowed_without_api_key_when_unset(self):
        res = self.client.post("/cases/CASE-001/review?llm_mode=mock")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["case_id"], "CASE-001")

    def test_live_review_forbidden_when_api_key_unset(self):
        os.environ["GEMINI_API_KEY"] = "fake-gemini"
        os.environ["LLM_MODE"] = "live"
        get_settings.cache_clear()
        res = self.client.post("/cases/CASE-001/review?llm_mode=live")
        self.assertEqual(res.status_code, 403)
        self.assertIn("REVIEW_API_KEY", res.json()["detail"])

    def test_review_requires_key_when_configured(self):
        os.environ["REVIEW_API_KEY"] = "test-secret"
        get_settings.cache_clear()
        denied = self.client.post("/cases/CASE-001/review?llm_mode=mock")
        self.assertEqual(denied.status_code, 401)
        ok = self.client.post(
            "/cases/CASE-001/review?llm_mode=mock",
            headers={"X-API-Key": "test-secret"},
        )
        self.assertEqual(ok.status_code, 200)

    def test_batch_requires_api_key(self):
        res = self.client.post("/reviews/batch?llm_mode=mock")
        self.assertEqual(res.status_code, 403)

        os.environ["REVIEW_API_KEY"] = "test-secret"
        get_settings.cache_clear()
        ok = self.client.post(
            "/reviews/batch?llm_mode=mock",
            headers={"X-API-Key": "test-secret"},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertGreaterEqual(len(ok.json()), 1)

    def test_live_batch_opt_in(self):
        os.environ["REVIEW_API_KEY"] = "test-secret"
        os.environ["GEMINI_API_KEY"] = "fake-gemini"
        os.environ["ALLOW_LIVE_BATCH"] = "false"
        get_settings.cache_clear()
        res = self.client.post(
            "/reviews/batch?llm_mode=live",
            headers={"X-API-Key": "test-secret"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("ALLOW_LIVE_BATCH", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
