"""Deterministic offline stand-in for the SOP-03 comparison.

It reads the same prompt the live model receives and answers with the same JSON schema,
so the guard/validation path is exercised identically without an API key. It is a small
synonym table plus uncertainty keywords, not a clinical terminology service.
"""

from __future__ import annotations

import json
import re
import string
import time

from pydantic import BaseModel

from ..normalize import has_uncertainty_marker
from .base import LLMResponse

SYNONYMS = (
    ("t2dm", "type 2 diabetes mellitus"),
    ("dm2", "type 2 diabetes mellitus"),
    ("type ii", "type 2"),
    ("uncomplicated", "without complications"),
    ("without documented complications", "without complications"),
    ("cap", "community-acquired pneumonia"),
    ("gi", "gastrointestinal"),
)
STOPWORDS = {"with", "and", "the", "of", "a", "an", "no"}
_FIELD_RE = re.compile(r'<field id="(?P<id>[A-Z_]+)"[^>]*>(?P<value>.*?)</field>', re.S)


def _canon_tokens(text: str) -> set[str]:
    t = text.lower()
    for short, full in SYNONYMS:
        t = re.sub(rf"\b{re.escape(short)}\b", full, t)
    t = t.translate(str.maketrans(string.punctuation.replace("-", ""), " " * (len(string.punctuation) - 1)))
    return {w for w in t.split() if w not in STOPWORDS}


_uncertain = has_uncertainty_marker


def mock_assessment(fields: dict[str, str]) -> dict:
    claim = fields.get("CLAIM", "")
    discharge = fields.get("DISCHARGE_SUMMARY", "")
    note = fields.get("PHYSICIAN_NOTE", "")
    final_source, final = ("DISCHARGE_SUMMARY", discharge) if discharge else ("PHYSICIAN_NOTE", note)
    final_status = "suspected" if _uncertain(final) else ("confirmed" if final else "unclear")
    working_status = ("suspected" if _uncertain(note) else "confirmed") if note else "not_available"
    claim_status = "suspected" if _uncertain(claim) else "confirmed"
    claim_tokens, final_tokens = _canon_tokens(claim), _canon_tokens(final)

    if not final:
        relationship, rationale = "insufficient_evidence", "No record diagnosis available to compare."
    elif final_status != "confirmed" and claim_status == "confirmed" and claim_tokens & final_tokens:
        relationship = "claim_more_certain_than_record"
        rationale = "The claim states the diagnosis as confirmed while the record marks it as uncertain."
    elif claim_tokens and (claim_tokens <= final_tokens or final_tokens <= claim_tokens):
        relationship, rationale = "equivalent", "Same condition after expanding standard abbreviations."
    else:
        relationship, rationale = "conflict", "The claim names a different condition from the final record diagnosis."

    evidence = [{"source": "CLAIM", "quote": claim}] if claim else []
    if final:
        evidence.append({"source": final_source, "quote": final})
    return {
        "relationship": relationship,
        "final_record_diagnosis_status": final_status,
        "working_diagnosis_status": working_status,
        "claim_diagnosis_status": claim_status,
        "evidence": evidence,
        "rationale": f"[mock] {rationale}",
        "confidence": 0.9,
    }


class MockClient:
    provider = "mock"

    def __init__(self, model: str = "mock-sop03-heuristic"):
        self.model = model

    def generate_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResponse:
        started = time.perf_counter()
        fields = {m.group("id"): m.group("value").strip() for m in _FIELD_RE.finditer(user)}
        text = json.dumps(mock_assessment(fields))
        return LLMResponse(
            text=text,
            input_tokens=(len(system) + len(user)) // 4,
            output_tokens=len(text) // 4,
            thinking_tokens=0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=self.model,
            token_source="estimated",
        )
