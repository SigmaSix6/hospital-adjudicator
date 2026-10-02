"""CLI helper (the API is the product interface).

    python -m review_assistant.cli review CASE-001 [--llm-mode mock] [--no-cache]
    python -m review_assistant.cli review --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import get_settings
from .ingestion import list_case_ids
from .pipeline import review_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review-assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    rv = sub.add_parser("review", help="Review one case or all cases")
    rv.add_argument("case_id", nargs="?")
    rv.add_argument("--all", action="store_true")
    rv.add_argument("--llm-mode", choices=["live", "mock"])
    rv.add_argument("--no-cache", action="store_true")
    rv.add_argument("--run-label", default="cli")
    rv.add_argument("--out-dir", default="outputs")
    args = parser.parse_args(argv)

    settings = get_settings()
    if not args.all and not args.case_id:
        parser.error("give a case_id or --all")
    case_ids = list_case_ids(settings.data_dir) if args.all else [args.case_id.upper()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        result = review_case(case_id, llm_mode=args.llm_mode, use_cache=not args.no_cache,
                             run_label=args.run_label, settings=settings)
        (out_dir / f"{case_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"{case_id}: {result.status:16s} findings={len(result.findings)} -> {out_dir / (case_id + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
