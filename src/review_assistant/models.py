"""Pydantic models: parsed documents, findings, and the API response contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CaseStatus = Literal["no_issues_found", "needs_review"]
Severity = Literal["high", "medium", "low"]
Category = Literal[
    "missing_document",
    "missing_field",
    "identity_mismatch",
    "date_inconsistency",
    "diagnosis_conflict",
    "diagnosis_uncertain",
    "incomplete_report",
    "undetermined",
    "observation",
]
Basis = Literal["documented_fact", "model_judgment"]
CheckOutcome = Literal["pass", "issue", "not_applicable", "undetermined"]


# --------------------------------------------------------------------------- documents


class ExtractedValue(BaseModel):
    """One value read from a document, with enough provenance to find it again."""

    name: str
    value: str
    location: str = Field(description="e.g. 'table 1, row 3' or \"section 'Assessment'\"")


class ParsedDocument(BaseModel):
    case_id: str
    document_type: str
    file: str = Field(description="Path relative to the data directory")
    sha256: str
    title: str
    fields: list[ExtractedValue]
    sections: list[ExtractedValue]

    def field(self, name: str) -> ExtractedValue | None:
        key = name.strip().lower()
        return next((f for f in self.fields if f.name.strip().lower() == key), None)

    def section(self, name: str) -> ExtractedValue | None:
        key = name.strip().lower()
        return next((s for s in self.sections if s.name.strip().lower() == key), None)

    def lookup(self, name: str) -> ExtractedValue | None:
        return self.field(name) or self.section(name)


class ManifestEntry(BaseModel):
    case_id: str
    document_type: str
    relative_path: str


class CaseBundle(BaseModel):
    case_id: str
    manifest_entries: list[ManifestEntry]
    documents: list[ParsedDocument]
    load_errors: list[str] = []

    def get(self, document_type: str) -> ParsedDocument | None:
        return next((d for d in self.documents if d.document_type == document_type), None)


# --------------------------------------------------------------------------- policies


class SopSection(BaseModel):
    heading: str
    text: str


class Sop(BaseModel):
    sop_id: str
    title: str
    file: str
    version: str
    sections: list[SopSection]

    def full_text(self) -> str:
        body = "\n".join(f"{s.heading}: {s.text}" for s in self.sections)
        return f"{self.sop_id} {self.title}\n{body}"


class PolicyRef(BaseModel):
    sop_id: str
    title: str
    section: str
    version: str
    excerpt: str


# --------------------------------------------------------------------------- results


class Evidence(BaseModel):
    document_type: str
    file: str
    field: str
    value: str = Field(description="Verbatim value or quote; empty string means the field is blank")
    location: str
    note: str | None = None


class Finding(BaseModel):
    finding_id: str
    rule_id: str
    category: Category
    severity: Severity
    title: str
    description: str
    policy_refs: list[PolicyRef]
    evidence: list[Evidence]
    basis: Basis
    confidence: float | None = None
    requires_human_review: bool


class CheckResult(BaseModel):
    rule_id: str
    sop_id: str
    description: str
    outcome: CheckOutcome
    detail: str


class LLMCallSummary(BaseModel):
    step: str
    provider: str
    model: str
    cache_status: Literal["hit", "miss", "disabled"]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    retries: int
    status: Literal["ok", "invalid_output", "error"]
    token_source: Literal["provider_usage_metadata", "estimated", "none"]


class DocumentSummary(BaseModel):
    document_type: str
    file: str
    sha256: str
    field_count: int
    section_count: int


class AuditRecord(BaseModel):
    run_id: str
    case_id: str
    timestamp: str
    run_label: str
    rule_set_version: str
    prompt_version: str
    llm_mode: str
    llm_model: str
    sop_versions: dict[str, str]
    input_documents: list[DocumentSummary]


class ReviewResult(BaseModel):
    case_id: str
    run_id: str
    status: CaseStatus
    summary: str
    human_review_required: bool
    human_review_reasons: list[str]
    findings: list[Finding]
    checks: list[CheckResult]
    uncertainties: list[str]
    documents_processed: list[DocumentSummary]
    llm_calls: list[LLMCallSummary]
    audit: AuditRecord
    decision_boundary: str = (
        "This assistant identifies issues and summarises evidence only. It does not approve, "
        "reject, or deny claims (SOP-06). 'no_issues_found' means no configured rule detected "
        "an issue; it is not an approval."
    )
