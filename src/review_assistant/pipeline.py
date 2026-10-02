"""Review orchestrator: ingest -> deterministic rules -> SOP-03 LLM step -> SOP-06 decision assembly."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from .config import PROMPT_VERSION, RULE_SET_VERSION, Settings, get_settings
from .diagnosis import CallContext, run_diagnosis_check
from .ingestion import load_case
from .llm import get_llm_client
from .llm.calllog import append_jsonl, utc_now
from .models import AuditRecord, DocumentSummary, Finding, ReviewResult
from .rules import run_deterministic_rules
from .sops import SopRegistry

log = logging.getLogger("review_assistant")
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def configure_logging(settings: Settings) -> None:
    if getattr(configure_logging, "_done", False):
        return
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(settings.app_log, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    configure_logging._done = True


def _event(event: str, **fields) -> None:
    log.info(json.dumps({"ts": utc_now(), "event": event, **fields}))


def _summary(status: str, findings: list[Finding]) -> str:
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("high", "medium", "low")}
    if status == "no_issues_found":
        extra = f" {counts['low']} informational observation(s) noted." if counts["low"] else ""
        return ("No review-triggering issues were detected by the configured SOP rules." + extra +
                " This is not an approval (SOP-06).")
    top = [f.title for f in findings if f.requires_human_review][:3]
    return (f"Needs human review: {counts['high']} high, {counts['medium']} medium, {counts['low']} low "
            f"severity finding(s). Main issues: {'; '.join(top)}.")


def review_case(
    case_id: str,
    llm_mode: str | None = None,
    use_cache: bool = True,
    run_label: str = "adhoc",
    settings: Settings | None = None,
) -> ReviewResult:
    settings = settings or get_settings()
    configure_logging(settings)
    run_id = uuid.uuid4().hex[:12]
    bundle = load_case(settings.data_dir, case_id)
    sops = SopRegistry(settings.data_dir)
    client, mode = get_llm_client(settings, llm_mode)
    _event("review_started", run_id=run_id, case_id=case_id, llm_mode=mode, run_label=run_label,
           documents=len(bundle.documents))

    output = run_deterministic_rules(bundle, sops)
    dx_output, calls = run_diagnosis_check(
        bundle, sops, client, settings, CallContext(run_id=run_id, case_id=case_id, run_label=run_label, use_cache=use_cache)
    )
    output.extend(dx_output)

    findings = sorted(output.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id))
    for i, f in enumerate(findings, start=1):
        f.finding_id = f"{case_id}-F{i:02d}"

    reasons = [f"[{f.severity}] {f.rule_id}: {f.title}" for f in findings if f.requires_human_review]
    status = "needs_review" if reasons else "no_issues_found"
    docs = [DocumentSummary(document_type=d.document_type, file=d.file, sha256=d.sha256,
                            field_count=len(d.fields), section_count=len(d.sections)) for d in bundle.documents]
    audit = AuditRecord(
        run_id=run_id, case_id=case_id, timestamp=utc_now(), run_label=run_label,
        rule_set_version=RULE_SET_VERSION, prompt_version=PROMPT_VERSION, llm_mode=mode,
        llm_model=client.model, sop_versions=sops.versions(), input_documents=docs,
    )
    result = ReviewResult(
        case_id=case_id, run_id=run_id, status=status, summary=_summary(status, findings),
        human_review_required=bool(reasons), human_review_reasons=reasons, findings=findings,
        checks=output.checks, uncertainties=output.uncertainties, documents_processed=docs,
        llm_calls=calls, audit=audit,
    )
    _persist(result, settings)
    _event("review_completed", run_id=run_id, case_id=case_id, status=status,
           findings=[f.rule_id for f in findings], llm_calls=len(calls),
           cost_usd=round(sum(c.cost_usd for c in calls), 6))
    return result


def _persist(result: ReviewResult, settings: Settings) -> None:
    case_dir = settings.reviews_dir / result.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump_json(indent=2)
    (case_dir / f"{result.run_id}.json").write_text(payload, encoding="utf-8")
    (case_dir / "latest.json").write_text(payload, encoding="utf-8")
    append_jsonl(settings.audit_log, {
        **result.audit.model_dump(),
        "status": result.status,
        "finding_rule_ids": [f.rule_id for f in result.findings],
        "output_file": str(Path("reviews") / result.case_id / f"{result.run_id}.json"),
        "human_review_outcome": None,
    })


def latest_review(case_id: str, settings: Settings | None = None) -> ReviewResult | None:
    settings = settings or get_settings()
    path = settings.reviews_dir / case_id / "latest.json"
    if not path.is_file():
        return None
    return ReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
