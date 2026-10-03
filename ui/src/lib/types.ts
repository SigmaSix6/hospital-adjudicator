export type CaseStatus = "no_issues_found" | "needs_review";
export type Severity = "high" | "medium" | "low";
export type CheckOutcome = "pass" | "issue" | "not_applicable" | "undetermined";
export type LlmMode = "live" | "mock";

export interface Health {
  status: string;
  version: string;
  default_llm_mode: LlmMode;
  gemini_configured: boolean;
  gemini_model: string;
  review_api_key_configured: boolean;
  allow_live_batch: boolean;
  rule_set_version: string;
  prompt_version: string;
}

export interface CaseListItem {
  case_id: string;
  document_types: string[];
  document_count: number;
  missing_core_documents: string[];
  latest_status: CaseStatus | null;
  latest_run_id: string | null;
  latest_reviewed_at: string | null;
  latest_finding_count: number | null;
  latest_high_count: number | null;
}

export interface ExtractedValue {
  name: string;
  value: string;
  location: string;
}

export interface ParsedDocument {
  case_id: string;
  document_type: string;
  file: string;
  sha256: string;
  title: string;
  fields: ExtractedValue[];
  sections: ExtractedValue[];
}

export interface CaseDetail {
  case_id: string;
  documents: ParsedDocument[];
  load_errors: string[];
}

export interface PolicyRef {
  sop_id: string;
  title: string;
  section: string;
  version: string;
  excerpt: string;
}

export interface Evidence {
  document_type: string;
  file: string;
  field: string;
  value: string;
  location: string;
  note: string | null;
}

export interface Finding {
  finding_id: string;
  rule_id: string;
  category: string;
  severity: Severity;
  title: string;
  description: string;
  policy_refs: PolicyRef[];
  evidence: Evidence[];
  basis: "documented_fact" | "model_judgment";
  confidence: number | null;
  requires_human_review: boolean;
}

export interface CheckResult {
  rule_id: string;
  sop_id: string;
  description: string;
  outcome: CheckOutcome;
  detail: string;
}

export interface LlmCall {
  step: string;
  provider: string;
  model: string;
  cache_status: "hit" | "miss" | "disabled";
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  retries: number;
  status: string;
  token_source: string;
}

export interface DocumentSummary {
  document_type: string;
  file: string;
  sha256: string;
  field_count: number;
  section_count: number;
}

export interface AuditRecord {
  run_id: string;
  case_id: string;
  timestamp: string;
  run_label: string;
  rule_set_version: string;
  prompt_version: string;
  llm_mode: string;
  llm_model: string;
  sop_versions: Record<string, string>;
  input_documents: DocumentSummary[];
}

export interface ReviewResult {
  case_id: string;
  run_id: string;
  status: CaseStatus;
  summary: string;
  human_review_required: boolean;
  human_review_reasons: string[];
  findings: Finding[];
  checks: CheckResult[];
  uncertainties: string[];
  documents_processed: DocumentSummary[];
  llm_calls: LlmCall[];
  audit: AuditRecord;
  decision_boundary: string;
}

export interface LlmCallsResponse {
  pricing_source: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}
