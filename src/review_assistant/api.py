"""HTTP API. Run with: uvicorn review_assistant.api:app --port 8741"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .config import PRICING_SOURCE, PROMPT_VERSION, RULE_SET_VERSION, get_settings
from .ingestion import CaseNotFoundError, list_case_ids, load_case, load_manifest
from .live_guard import (
    live_spend_guard,
    require_api_key,
    require_api_key_if_configured,
    resolve_llm_mode,
)
from .llm.calllog import read_jsonl
from .models import ManifestEntry, ParsedDocument, ReviewResult, Sop
from .pipeline import configure_logging, latest_review, review_case
from .rules import REQUIRED_DOCUMENTS
from .sops import load_sops

settings = get_settings()
configure_logging(settings)

app = FastAPI(
    title="Clinical Document Review Assistant",
    version=__version__,
    description=(
        "Reviews one synthetic patient case at a time against hospital SOPs and returns structured "
        "findings with evidence. It never approves, rejects, or denies a claim (SOP-06). "
        "Live LLM and batch endpoints require REVIEW_API_KEY (X-API-Key)."
    ),
)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"]
)

LlmMode = Literal["live", "mock"]


class Health(BaseModel):
    status: str
    version: str
    default_llm_mode: str
    gemini_configured: bool
    gemini_model: str
    review_api_key_configured: bool
    allow_live_batch: bool
    rule_set_version: str
    prompt_version: str


class CaseListItem(BaseModel):
    case_id: str
    document_types: list[str]
    document_count: int
    missing_core_documents: list[str]
    latest_status: str | None
    latest_run_id: str | None
    latest_reviewed_at: str | None
    latest_finding_count: int | None
    latest_high_count: int | None


class CaseDetail(BaseModel):
    case_id: str
    manifest_entries: list[ManifestEntry]
    documents: list[ParsedDocument]
    load_errors: list[str]


class BatchItem(BaseModel):
    case_id: str
    status: str | None
    run_id: str | None
    findings: int
    error: str | None = None


class LlmCallsResponse(BaseModel):
    pricing_source: str
    calls: list[dict]
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


def _case_or_404(case_id: str):
    s = get_settings()
    try:
        return load_case(s.data_dir, case_id.upper())
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown case_id '{case_id}'. See GET /cases.")


def _ensure_live_possible(mode: str, s) -> None:
    if mode == "live" and not s.gemini_configured:
        raise HTTPException(
            status_code=400,
            detail="llm_mode=live requested but GEMINI_API_KEY is not set. Use llm_mode=mock.",
        )


@app.get("/health", response_model=Health)
def health() -> Health:
    s = get_settings()
    return Health(
        status="ok",
        version=__version__,
        default_llm_mode=s.effective_llm_mode,
        gemini_configured=s.gemini_configured,
        gemini_model=s.gemini_model,
        review_api_key_configured=s.review_api_key_configured,
        allow_live_batch=s.allow_live_batch,
        rule_set_version=RULE_SET_VERSION,
        prompt_version=PROMPT_VERSION,
    )


@app.get("/cases", response_model=list[CaseListItem])
def list_cases() -> list[CaseListItem]:
    s = get_settings()
    manifest = load_manifest(s.data_dir)
    items = []
    for case_id in list_case_ids(s.data_dir):
        types = [e.document_type for e in manifest if e.case_id == case_id]
        latest = latest_review(case_id, s)
        items.append(CaseListItem(
            case_id=case_id, document_types=types, document_count=len(types),
            missing_core_documents=[t for t in REQUIRED_DOCUMENTS if t not in types],
            latest_status=latest.status if latest else None,
            latest_run_id=latest.run_id if latest else None,
            latest_reviewed_at=latest.audit.timestamp if latest else None,
            latest_finding_count=len(latest.findings) if latest else None,
            latest_high_count=sum(1 for f in latest.findings if f.severity == "high") if latest else None,
        ))
    return items


@app.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str) -> CaseDetail:
    bundle = _case_or_404(case_id)
    return CaseDetail(case_id=bundle.case_id, manifest_entries=bundle.manifest_entries,
                      documents=bundle.documents, load_errors=bundle.load_errors)


@app.post("/cases/{case_id}/review", response_model=ReviewResult)
def review(
    case_id: str,
    request: Request,
    llm_mode: LlmMode | None = Query(None, description="Override the default LLM mode. 'live' needs GEMINI_API_KEY and REVIEW_API_KEY."),
    use_cache: bool = Query(True, description="Reuse cached LLM responses for identical prompts"),
    run_label: str = Query("adhoc", max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"),
) -> ReviewResult:
    s = get_settings()
    _case_or_404(case_id)
    mode = resolve_llm_mode(llm_mode, s)
    _ensure_live_possible(mode, s)

    if mode == "live":
        require_api_key(request, s, purpose="Live LLM reviews")
        with live_spend_guard.live_slot(s):
            return review_case(
                case_id.upper(), llm_mode=llm_mode, use_cache=use_cache, run_label=run_label, settings=s
            )

    require_api_key_if_configured(request, s)
    return review_case(
        case_id.upper(), llm_mode=llm_mode, use_cache=use_cache, run_label=run_label, settings=s
    )


@app.get("/cases/{case_id}/reviews/latest", response_model=ReviewResult)
def get_latest(case_id: str) -> ReviewResult:
    s = get_settings()
    _case_or_404(case_id)
    result = latest_review(case_id.upper(), s)
    if result is None:
        raise HTTPException(status_code=404, detail="This case has not been reviewed yet.")
    return result


@app.post("/reviews/batch", response_model=list[BatchItem])
def review_all(
    request: Request,
    llm_mode: LlmMode | None = Query(None),
    use_cache: bool = Query(True),
    run_label: str = Query("batch", max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"),
) -> list[BatchItem]:
    s = get_settings()
    require_api_key(request, s, purpose="Batch reviews")
    mode = resolve_llm_mode(llm_mode, s)
    _ensure_live_possible(mode, s)
    case_ids = list_case_ids(s.data_dir)

    if mode == "live":
        if not s.allow_live_batch:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Live batch reviews are disabled. Set ALLOW_LIVE_BATCH=true, "
                    "or review cases individually via POST /cases/{id}/review."
                ),
            )
        live_spend_guard.reserve(s, n=max(len(case_ids), 1))

    out = []
    for case_id in case_ids:
        try:
            if mode == "live":
                with live_spend_guard.live_slot(s, reserved=True):
                    r = review_case(
                        case_id, llm_mode=llm_mode, use_cache=use_cache, run_label=run_label, settings=s
                    )
            else:
                r = review_case(
                    case_id, llm_mode=llm_mode, use_cache=use_cache, run_label=run_label, settings=s
                )
            out.append(BatchItem(case_id=case_id, status=r.status, run_id=r.run_id, findings=len(r.findings)))
        except HTTPException:
            raise
        except Exception as exc:  # one bad case must not abort the batch
            out.append(BatchItem(case_id=case_id, status=None, run_id=None, findings=0, error=type(exc).__name__))
    return out


@app.get("/policies", response_model=list[Sop])
def policies() -> list[Sop]:
    return list(load_sops(get_settings().data_dir).values())


@app.get("/llm-calls", response_model=LlmCallsResponse)
def llm_calls(request: Request, limit: int = Query(200, ge=1, le=5000)) -> LlmCallsResponse:
    s = get_settings()
    require_api_key_if_configured(request, s)
    rows = read_jsonl(s.llm_call_log)
    return LlmCallsResponse(
        pricing_source=PRICING_SOURCE, calls=rows[-limit:][::-1], total_calls=len(rows),
        total_input_tokens=sum(r.get("input_tokens", 0) for r in rows),
        total_output_tokens=sum(r.get("output_tokens", 0) for r in rows),
        total_cost_usd=round(sum(r.get("cost_usd", 0.0) for r in rows), 6),
    )
