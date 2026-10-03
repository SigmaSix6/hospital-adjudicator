"""Evaluate the review API against the candidate-authored gold set.

    python eval/run_eval.py --base-url http://127.0.0.1:8741 --llm-mode live
    python eval/run_eval.py --llm-mode live --stability 5 --compare-mock --report docs/evidence/eval-report.md

Hard gates (exit code 1 if any fails):
  * case-status accuracy = 100%
  * escalation recall on expected high-severity findings = 100%
  * zero review-triggering findings on the clean cases (CASE-001, CASE-006)
  * evidence validity = 100% (every evidence item resolves to a real document field/section and value)
Reported, not gated: finding precision/recall, mock-vs-live SOP-03 agreement, verdict stability.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
CLEAN_CASES = ("CASE-001", "CASE-006")


def norm(s: str) -> str:
    return " ".join((s or "").lower().split()).strip(" .;,")


def key(f: dict) -> tuple:
    return (f["rule_id"], f["category"], f["severity"])


def match_findings(expected: list[dict], optional: list[dict], actual: list[dict]) -> tuple[int, int, int, list[str]]:
    """Return (tp, fp, fn, notes) over review-triggering findings."""
    remaining = [key(f) for f in actual if f["requires_human_review"]]
    opt = {key(o) for o in optional}
    tp = fn = 0
    notes = []
    for exp in expected:
        options = [key(o) for o in exp["any_of"]] if "any_of" in exp else [key(exp)]
        hit = next((o for o in options if o in remaining), None)
        if hit:
            tp += 1
            remaining.remove(hit)
        else:
            fn += 1
            notes.append(f"missed {options[0]}")
    extra = [r for r in remaining if r not in opt]
    notes += [f"unexpected {r}" for r in extra]
    return tp, len(extra), fn, notes


def evidence_valid(result: dict, docs: dict[str, dict]) -> tuple[int, int, list[str]]:
    ok = total = 0
    problems = []
    for f in result["findings"]:
        for ev in f["evidence"]:
            total += 1
            if ev["file"] == "case_manifest.csv":
                ok += 1
                continue
            doc = docs.get(ev["file"])
            if doc is None:
                problems.append(f"{f['finding_id']}: unknown file {ev['file']}")
                continue
            items = {norm(x["name"]): x["value"] for x in doc["fields"] + doc["sections"]}
            actual = items.get(norm(ev["field"]))
            if actual is None:
                if ev["value"] == "" and "not present" in ev["location"]:
                    ok += 1
                else:
                    problems.append(f"{f['finding_id']}: field '{ev['field']}' not in {ev['file']}")
                continue
            if norm(ev["value"]) == norm(actual) or (ev["value"] and norm(ev["value"]) in norm(actual)):
                ok += 1
            else:
                problems.append(f"{f['finding_id']}: value mismatch for {ev['field']}")
    return ok, total, problems


def sop03_verdict(result: dict) -> str:
    check = next((c for c in result["checks"] if c["rule_id"] == "SOP-03.R1"), None)
    if not check:
        return "n/a"
    if check["outcome"] == "pass":
        return "equivalent" if "LLM not called" not in check["detail"] else "exact_match"
    rules = {f["rule_id"] for f in result["findings"]}
    if "SOP-03.R1" in rules:
        return "conflict"
    if "SOP-03.R2" in rules:
        return "claim_more_certain"
    return check["outcome"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8741")
    ap.add_argument("--llm-mode", choices=["live", "mock"], default=None)
    ap.add_argument("--api-key", default=os.getenv("REVIEW_API_KEY"), help="REVIEW_API_KEY (or set env)")
    ap.add_argument("--use-cache", action="store_true", help="Allow cached LLM responses (default: disabled)")
    ap.add_argument("--stability", type=int, default=0, help="Repeat LLM cases N times (cache disabled)")
    ap.add_argument("--compare-mock", action="store_true", help="Also run mock and compare SOP-03 verdicts")
    ap.add_argument("--report", default=None, help="Write a Markdown report to this path")
    args = ap.parse_args()

    gold = yaml.safe_load((ROOT / "eval" / "expected.yaml").read_text())
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    client = httpx.Client(base_url=args.base_url, timeout=180, headers=headers)
    health = client.get("/health").json()
    mode = args.llm_mode or health["default_llm_mode"]
    label = "eval-live" if mode == "live" else "eval-mock"
    if mode == "live" and not args.api_key:
        print("error: live eval requires REVIEW_API_KEY (--api-key or env).", file=sys.stderr)
        return 2

    def review(case_id: str, llm_mode: str, run_label: str, cache: bool) -> dict:
        resp = client.post(f"/cases/{case_id}/review",
                           params={"llm_mode": llm_mode, "use_cache": str(cache).lower(), "run_label": run_label})
        resp.raise_for_status()
        return resp.json()

    rows, results = [], {}
    tp = fp = fn = 0
    status_ok = high_expected = high_found = clean_fp = 0
    ev_ok = ev_total = 0
    ev_problems: list[str] = []
    for case_id, exp in gold.items():
        res = review(case_id, mode, label, args.use_cache)
        results[case_id] = res
        docs = {d["file"]: d for d in client.get(f"/cases/{case_id}").json()["documents"]}
        t, p, n, notes = match_findings(exp["findings"], exp.get("optional", []), res["findings"])
        tp, fp, fn = tp + t, fp + p, fn + n
        s_ok = res["status"] == exp["status"]
        status_ok += s_ok
        for e in exp["findings"]:
            options = e.get("any_of", [e])
            if any(o["severity"] == "high" for o in options):
                high_expected += 1
                if any(key(o) in {key(f) for f in res["findings"]} for o in options):
                    high_found += 1
        if case_id in CLEAN_CASES:
            clean_fp += sum(1 for f in res["findings"] if f["requires_human_review"])
        o, t_, probs = evidence_valid(res, docs)
        ev_ok, ev_total = ev_ok + o, ev_total + t_
        ev_problems += [f"{case_id} {p}" for p in probs]
        cost = sum(c["cost_usd"] for c in res["llm_calls"])
        rows.append((case_id, exp["status"], res["status"], "PASS" if s_ok and not notes else ("PASS*" if s_ok else "FAIL"),
                     ", ".join(f["rule_id"] for f in res["findings"]) or "-", len(res["llm_calls"]), cost, "; ".join(notes) or "-"))

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    gates = {
        "Case-status accuracy = 100%": status_ok == len(gold),
        "High-severity escalation recall = 100%": high_found == high_expected,
        "Zero review-triggering findings on clean cases": clean_fp == 0,
        "Evidence validity = 100%": ev_ok == ev_total,
    }

    stability_rows = []
    if args.stability:
        for case_id, exp in gold.items():
            if not exp.get("llm_case"):
                continue
            verdicts = Counter(sop03_verdict(review(case_id, mode, "stability", False)) for _ in range(args.stability))
            verdicts[sop03_verdict(results[case_id])] += 1
            top, n = verdicts.most_common(1)[0]
            stability_rows.append((case_id, dict(verdicts), f"{n}/{sum(verdicts.values())}"))

    mock_rows = []
    if args.compare_mock and mode == "live":
        for case_id, exp in gold.items():
            if exp.get("llm_case"):
                m = review(case_id, "mock", "eval-mock-compare", False)
                mock_rows.append((case_id, sop03_verdict(results[case_id]), sop03_verdict(m)))

    lines = [
        "# Evaluation Report", "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `eval/run_eval.py` against "
        f"`{args.base_url}`, LLM mode `{mode}` (model `{health['gemini_model'] if mode == 'live' else 'mock'}`), "
        f"cache {'enabled' if args.use_cache else 'disabled'}. Gold set: `eval/expected.yaml` (candidate-authored).", "",
        "## Gates", "", "| Gate | Result |", "|---|---|",
    ]
    lines += [f"| {g} | {'PASS' if ok else 'FAIL'} |" for g, ok in gates.items()]
    lines += [
        "", "## Metrics", "", "| Metric | Value |", "|---|---|",
        f"| Case-status accuracy | {status_ok}/{len(gold)} |",
        f"| High-severity escalation recall | {high_found}/{high_expected} |",
        f"| Finding precision (review-triggering) | {precision:.3f} ({tp} TP, {fp} FP) |",
        f"| Finding recall | {recall:.3f} ({tp} TP, {fn} FN) |",
        f"| Evidence validity | {ev_ok}/{ev_total} |",
        f"| Review-triggering findings on clean cases | {clean_fp} |",
        "", "## Per Case", "",
        "| Case | Expected | Actual | Result | Findings (rule IDs) | LLM calls | Cost (USD) | Notes |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]:.6f} | {r[7]} |" for r in rows]
    lines.append("\n`PASS*` = status correct but the finding set differs from gold (see Notes).")
    if stability_rows:
        lines += ["", f"## SOP-03 Verdict Stability ({args.stability + 1} runs per LLM case)", "",
                  "| Case | Verdict counts | Agreement |", "|---|---|---|"]
        lines += [f"| {c} | {v} | {a} |" for c, v, a in stability_rows]
    if mock_rows:
        agree = sum(1 for _, l, m in mock_rows if l == m)
        lines += ["", f"## Mock vs Live SOP-03 Agreement: {agree}/{len(mock_rows)}", "",
                  "| Case | Live verdict | Mock verdict |", "|---|---|---|"]
        lines += [f"| {c} | {l} | {m} |" for c, l, m in mock_rows]
    if ev_problems:
        lines += ["", "## Evidence Problems", ""] + [f"- {p}" for p in ev_problems]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(report, encoding="utf-8")
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
