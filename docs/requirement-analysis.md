# Requirement Analysis

Sources: the technical-test brief (cited as **Brief §section**), the candidate package `README.md`,
`data_dictionary.md`, `case_manifest.csv`, the 41 case documents and SOP-01 to SOP-07 (copied
unchanged into `data/`).

## 1. Problem Understanding

**Workflow today.** Before a patient case goes to internal review or a payer claim, a hospital
reviewer opens every document in the case, checks that the required documents and fields are
present, checks that identity, dates and diagnoses agree, looks up the relevant SOP, and decides
whether the case needs a closer human look.

**Users.**
- *Primary:* the document reviewer (claims or medical-records staff). They need a short list of
  issues per case, each with the exact document field it came from and the SOP clause behind it.
- *Secondary:* the reviewer's supervisor or auditor, who needs to reconstruct later what the
  system saw and why it said what it said (SOP-07).
- *Integrators:* downstream claim/workflow systems that consume the JSON (Brief "Required Product Interface").

**Decision being supported.** "Does this case need human review, and why?" The assistant does
**not** make the claim decision. SOP-06 forbids approving, rejecting or denying. The output is
triage plus evidence.

**Desired outcome.** Reviewers spend their time on the cases and fields that matter. Every
flagged issue can be verified in seconds, and nothing that an SOP says must be escalated is
silently passed.

## 2. Functional Requirements

| ID | Requirement | Source |
|---|---|---|
| FR-01 | Accept or identify one patient case via an **API**, process all its documents, return structured JSON. A CLI is only a helper. | Brief "Required Product Interface"; package README |
| FR-02 | Treat `case_manifest.csv` as the source of truth for which documents exist. | data_dictionary.md |
| FR-03 | Extract identity, encounter dates, diagnoses, claimed procedure, signature, and report sections from `.docx` tables **and** narrative sections (Assessment, Findings, Impression live in headings/paragraphs, not the table). | Brief Task 2; documents |
| FR-04 | Check required documents and required claim fields; never infer missing content. | SOP-01 |
| FR-05 | Patient ID and DOB must match exactly across documents (high severity); names may be normalised. | SOP-02 |
| FR-06 | Compare claim diagnosis with the final documented diagnosis: equivalent wording is not a conflict, different conditions are, and a claim that is more certain than the record escalates. | SOP-03 |
| FR-07 | Discharge on or after admission (high severity if not); procedure dates within the stay. | SOP-04 |
| FR-08 | Listed procedures need their supporting report (high severity if missing); blank required sections mean an incomplete report. | SOP-05 |
| FR-09 | Escalate on conflicting evidence, uncertain diagnosis, incomplete evidence, identity mismatch, or an undeterminable rule outcome; output `needs_review`, never approve/reject. | SOP-06 |
| FR-10 | Every finding cites document + field/section + value, and separates documented facts from model judgment. | SOP-07 |
| FR-11 | Response contains case-level status, all findings, rule/policy references, evidence, uncertainty and human-review reasons. | Brief "Required Product Interface" |
| FR-12 | All 10 supplied cases are runnable through the API. | Brief |
| FR-13 | Per-LLM-call usage log (provider/model, tokens, cost, latency, retries, cache status) with per-case and overall totals. | Brief "Expected Deliverables" |
| FR-14 | Safe secret handling with a mock/fallback when no API key is present. | Brief "Technical Expectations" |

## 3. Non-Functional Requirements

| Area | Requirement and how it is met |
|---|---|
| Reliability | A model failure must never produce a false "no issues". Timeouts, invalid JSON, schema violations and unverifiable quotes all become a `needs_review` finding (SOP-06.R1). Per-attempt timeout 10 s, up to 3 retries with backoff. |
| Determinism | Rules with an exact SOP definition are code. The single LLM step runs at temperature 0 with an enum-only verdict; measured stability is 5/5 on all six LLM cases (`docs/evidence/eval-report.md`). |
| Performance | Deterministic-only reviews take tens of milliseconds. LLM reviews take about 1.5–3 s per call when healthy. Observed provider hangs push some calls to 10–15 s through retries (see cost summary). |
| Security & privacy | Keys only in env/`.env` (gitignored). Only diagnosis/assessment text is sent to the LLM; never name, Patient ID or DOB. Logs hold token counts and hashes, not document text. Document text is wrapped as untrusted data in the prompt. |
| Observability | JSON event log (`var/logs/app.log`) keyed by `run_id`; per-call LLM log (`llm_calls.jsonl`); audit log (`audit.jsonl`); every response is persisted under `var/reviews/`. |
| Explainability | Each finding lists rule ID, SOP section with the quoted policy text, evidence rows, basis (`documented_fact` / `model_judgment`) and confidence. A `checks[]` array shows passed checks too. |
| Maintainability | Small typed modules (ingestion, rules, diagnosis, pipeline, API). Pydantic models are both the API contract and the LLM output validator. |
| Cost | One small-model call per case at most, skipped when unnecessary. Measured cost is about USD 0.00028 per case. |

## 4. Ambiguities and Open Questions

| ID | Ambiguity or Question | Why It Matters | Proposed Clarification |
|---|---|---|---|
| RQ-01 | The SOPs only name `needs_review`. What is the other status, and is there a severity scale? | Downstream systems need a closed vocabulary, and a "pass" must not read as approval. | Two statuses: `no_issues_found` / `needs_review`. Three severities: `high` / `medium` / `low`. Confirm with operations. |
| RQ-02 | Which document holds the "final documented diagnosis" (SOP-03)? | CASE-004: the physician note says "Stable angina suspected", but the discharge summary and the claim say "Stable angina". | Use the Discharge Summary's Primary Diagnosis. The physician note is the working diagnosis (A-03). |
| RQ-03 | Does "physician signature" = "Not signed" count as a missing required field? | CASE-010. SOP-01 lists the signature as required, but the field is filled in. | Yes, a recorded absence of a required signature is treated as missing (A-02). |
| RQ-04 | Is a report with a blank required section "missing" (high) or "incomplete" (review)? | CASE-010's radiology report has an empty Impression. | Incomplete, per the SOP-05 "Incomplete report" clause, so medium severity with review (A-04). |
| RQ-05 | Should identity be checked on documents that do not carry DOB (the physician note has no DOB)? | Treating a missing DOB as a mismatch would flag every case. | Compare only the documents that carry the field (A-05). |
| RQ-06 | Severity for SOP-01, SOP-03 and SOP-05-incomplete issues is not stated. | Prioritisation and gates. | `high` only where an SOP explicitly says high. Other mandatory escalations are `medium`. Informational notes are `low` (A-06). |
| RQ-07 | SOP-04 procedure-date exceptions ("unless a supporting note explicitly explains otherwise"): how is an explanation recognised? | False positives versus misses. | Flag out-of-window dates for review and let the reviewer confirm the note. Not exercised by the data. |
| RQ-08 | What does "patient identity" in SOP-01's required claim fields include? | Which blanks to flag. | Patient ID, Patient Name and Date of Birth. |
| RQ-09 | Should a missing Discharge Summary block the diagnosis comparison? | CASE-002. | No. Compare against the physician-note assessment, record an uncertainty, and the case is already `needs_review` via SOP-01. |
| RQ-10 | Is an API that takes a case ID enough, or must it accept uploads? | Scope. | A case ID against the bundled data meets "accept or identify one patient case". An upload endpoint is listed as production work. |
| RQ-11 | Are ordered-but-unclaimed investigations (CASE-001 chest radiograph) in scope for SOP-05? | False positives. | No. SOP-05 is triggered by the *claimed* procedure, and chest radiographs are not listed. |
| RQ-12 | Who acts on `needs_review`, what is the SLA, and is reviewer feedback captured? | It determines the online metrics and the audit fields. | Out of scope. The audit record reserves `human_review_outcome` for it. |

## 5. Assumptions

| ID | Assumption | Rationale | Risk if Incorrect | How to Validate |
|---|---|---|---|---|
| A-01 | Status vocabulary is `no_issues_found` / `needs_review`; there is no approve/reject. `no_issues_found` means "no configured rule fired", not approval. | SOP-06 decision boundary. | Consumers may read `no_issues_found` as approval. | Confirm wording with claims operations; the response carries an explicit `decision_boundary` string. |
| A-02 | "Not signed" on Physician Signature is a missing required claim field (SOP-01). | The signature is a required field, and "Not signed" records its absence. | Over-flagging if "Not signed" is a legitimate interim state. | Ask the claims team. |
| A-03 | The Discharge Summary Primary Diagnosis is the final documented diagnosis. A physician-note "suspected" that the discharge summary confirms is normal diagnostic progression: it is reported as a `low` observation and not escalated (CASE-004). | The note is written at admission; the discharge summary closes the encounter. | Missed escalation if reviewers expect any "suspected" anywhere to escalate. | Clinical documentation lead. Easy to flip: make SOP-03.R3 `requires_human_review=True`. |
| A-04 | A blank required section of an existing report is "incomplete" (medium, review), not "missing" (high). | SOP-05 has separate clauses for each. | Under-prioritised if the payer treats blank Impression as missing. | Payer rules. |
| A-05 | Identity fields are compared only across documents that carry them; a document lacking DOB is not a mismatch. | The physician notes carry no DOB by design. | None observed. | Data dictionary owner. |
| A-06 | Severity: `high` only where an SOP says so (SOP-02 ID/DOB, SOP-04 discharge before admission, SOP-05 missing report). Other SOP-06 mandatory escalations are `medium`. `low` is informational and does not trigger review. | Keeps severity traceable to policy text instead of my opinion. | A diagnosis conflict might deserve `high` operationally. | Review with operations; it is a one-line change per rule. |
| A-07 | Admission/discharge dates should agree across documents (SOP-04.R3, medium). | It is part of "basic chronological consistency". | Possible over-flagging. | Not triggered by the supplied data. |
| A-08 | Names are normalised for case, spacing, punctuation and common titles (including Indonesian titles such as Tn./Ny.). A name-only difference with matching ID and DOB is a `low` observation. | SOP-02 "Names". | None observed. | — |
| A-09 | The supplied data is synthetic, so sending diagnosis text to a public LLM API is acceptable here. Production needs a zero-retention or in-region endpoint. | Brief states the data is synthetic. | Not acceptable for real PHI. | Security/DPO review before any real data. |
| A-10 | The candidate-authored gold set (`eval/expected.yaml`) reflects these assumptions. | No labels are supplied. | The eval measures agreement with my reading, not ground truth. | Have a clinician label the 10 cases. |

## 6. Scope

### In Scope

- FastAPI service: `GET /health`, `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/review`,
  `GET /cases/{id}/reviews/latest`, `POST /reviews/batch`, `GET /policies`, `GET /llm-calls`.
- Manifest-driven `.docx` ingestion with per-value provenance (table row or section heading).
- Deterministic rules for SOP-01, 02, 04 and 05. Decision assembly per SOP-06. Evidence per SOP-07.
- One LLM step (SOP-03) on Google Gemini with structured output, quote verification, confidence
  floor, retries, cache, and a deterministic mock with the same interface.
- JSONL call log, audit log, app event log; generated `docs/cost-summary.md`.
- Evaluation script with gates, stability and mock-vs-live agreement.
- Docker / docker-compose; CLI helper; a reviewer web UI (extra, not required by the brief).

### Out of Scope

- Upload of arbitrary documents, OCR/scanned PDFs, layout detection (the package is clean `.docx`).
- Authentication/RBAC, multi-tenant storage, encryption at rest, data retention policies.
- Capturing the human reviewer's decision and feeding it back (the field is reserved in the audit record).
- Clinical terminology services (SNOMED/ICD mapping) and RAG over a large policy corpus.
- Automated unit tests (the brief says they are optional; the eval script covers behaviour end to end).

## 7. Success Criteria

| Dimension | Criterion | Result (live Gemini, `docs/evidence/eval-report.md`) |
|---|---|---|
| Correctness | Case-status accuracy 100% on the 10 cases | 10/10 |
| Escalation | Recall on expected high-severity findings = 100% (hard gate) | 4/4 |
| False positives | 0 review-triggering findings on the clean cases (CASE-001, CASE-006 trap) | 0 |
| Finding quality | Finding precision / recall vs gold | 1.00 / 1.00 (11/11) |
| Evidence | 100% of evidence items resolve to a real document field/section and value | 29/29 |
| LLM stability | Same SOP-03 verdict on repeated runs | 5/5 on all six LLM cases |
| Fallback | Mock agrees with live on SOP-03 verdicts | 6/6 |
| Reliability | No provider failure yields `no_issues_found` | Verified: a timed-out run escalated to `needs_review` (see architecture §7) |
| Latency | p50 below 5 s per review in live mode | p50 about 3 s per LLM call; deterministic-only reviews are under 100 ms |
| Cost | Below USD 0.01 per case | About USD 0.00028 per case |

## 8. Risks and Constraints

- **Gold set bias.** It was written by the same person who wrote the rules (A-10). Mitigation:
  assumptions are explicit and each one is a one-line config change.
- **Template brittleness.** The parser assumes a key/value table plus Heading-styled sections.
  Real documents (scans, free text, other templates) need format detection and OCR, and the LLM
  may need to take on extraction with provenance.
- **LLM variability and provider reliability.** In two full development runs, 25–42% of Gemini
  calls needed at least one retry because a request hung. Retries absorb this, and failures escalate. Production needs a second
  provider/region and alerting on retry rate.
- **Over-reliance on `no_issues_found`.** It covers only the configured rules. The UI and API state
  this explicitly.
- **Privacy.** Real PHI would need a BAA/DPA-covered, zero-retention endpoint and data-residency
  review (Indonesia PDP Law), plus access control on logs and stored reviews.
