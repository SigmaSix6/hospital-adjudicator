"""Run every manifest case through the HTTP API and save the JSON results.

    python scripts/run_cases_via_api.py --llm-mode live --run-label canonical-live --out-dir docs/evidence/reviews
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8741")
    ap.add_argument("--llm-mode", choices=["live", "mock"], default=None)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--run-label", default="api-run")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=180)
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    params = {"use_cache": str(not args.no_cache).lower(), "run_label": args.run_label}
    if args.llm_mode:
        params["llm_mode"] = args.llm_mode
    total_cost = 0.0
    for case in client.get("/cases").json():
        cid = case["case_id"]
        resp = client.post(f"/cases/{cid}/review", params=params)
        resp.raise_for_status()
        r = resp.json()
        cost = sum(c["cost_usd"] for c in r["llm_calls"])
        total_cost += cost
        calls = ", ".join(f"{c['provider']}:{c['cache_status']}:{c['latency_ms']}ms" for c in r["llm_calls"]) or "no LLM call"
        print(f"{cid}  {r['status']:16s} findings={[f['rule_id'] for f in r['findings']]}  [{calls}]  ${cost:.6f}")
        if out_dir:
            (out_dir / f"{cid}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"Total estimated cost: ${total_cost:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
