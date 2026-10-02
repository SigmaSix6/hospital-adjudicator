# Evaluation Report

Generated 2026-10-02T05:44:48+00:00 by `eval/run_eval.py` against `http://127.0.0.1:8741`, LLM mode `live` (model `gemini-3.1-flash-lite`), cache disabled. Gold set: `eval/expected.yaml` (candidate-authored).

## Gates

| Gate | Result |
|---|---|
| Case-status accuracy = 100% | PASS |
| High-severity escalation recall = 100% | PASS |
| Zero review-triggering findings on clean cases | PASS |
| Evidence validity = 100% | PASS |

## Metrics

| Metric | Value |
|---|---|
| Case-status accuracy | 10/10 |
| High-severity escalation recall | 4/4 |
| Finding precision (review-triggering) | 1.000 (11 TP, 0 FP) |
| Finding recall | 1.000 (11 TP, 0 FN) |
| Evidence validity | 29/29 |
| Review-triggering findings on clean cases | 0 |

## Per Case

| Case | Expected | Actual | Result | Findings (rule IDs) | LLM calls | Cost (USD) | Notes |
|---|---|---|---|---|---:|---:|---|
| CASE-001 | no_issues_found | no_issues_found | PASS | - | 0 | 0.000000 | - |
| CASE-002 | needs_review | needs_review | PASS | SOP-01.R1 | 1 | 0.000429 | - |
| CASE-003 | needs_review | needs_review | PASS | SOP-01.R2 | 0 | 0.000000 | - |
| CASE-004 | needs_review | needs_review | PASS | SOP-02.R1, SOP-03.R3 | 1 | 0.000469 | - |
| CASE-005 | needs_review | needs_review | PASS | SOP-03.R1 | 1 | 0.000470 | - |
| CASE-006 | no_issues_found | no_issues_found | PASS | - | 1 | 0.000435 | - |
| CASE-007 | needs_review | needs_review | PASS | SOP-04.R1 | 0 | 0.000000 | - |
| CASE-008 | needs_review | needs_review | PASS | SOP-05.R1 | 0 | 0.000000 | - |
| CASE-009 | needs_review | needs_review | PASS | SOP-03.R2 | 1 | 0.000505 | - |
| CASE-010 | needs_review | needs_review | PASS | SOP-02.R2, SOP-01.R2, SOP-03.R1, SOP-05.R2 | 1 | 0.000466 | - |

`PASS*` = status correct but the finding set differs from gold (see Notes).

## SOP-03 Verdict Stability (5 runs per LLM case)

| Case | Verdict counts | Agreement |
|---|---|---|
| CASE-002 | {'equivalent': 5} | 5/5 |
| CASE-004 | {'equivalent': 5} | 5/5 |
| CASE-005 | {'conflict': 5} | 5/5 |
| CASE-006 | {'equivalent': 5} | 5/5 |
| CASE-009 | {'claim_more_certain': 5} | 5/5 |
| CASE-010 | {'conflict': 5} | 5/5 |

## Mock vs Live SOP-03 Agreement: 6/6

| Case | Live verdict | Mock verdict |
|---|---|---|
| CASE-002 | equivalent | equivalent |
| CASE-004 | equivalent | equivalent |
| CASE-005 | conflict | conflict |
| CASE-006 | equivalent | equivalent |
| CASE-009 | claim_more_certain | claim_more_certain |
| CASE-010 | conflict | conflict |
