"""Per-call usage log (JSONL) and a file-based response cache.

The log stores token counts, cost, latency, retries and hashes only; no document text.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..config import MODEL_PRICING_USD_PER_1M

_lock = threading.Lock()


def compute_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """cost = input/1e6 * P_in + output/1e6 * P_out (output includes thinking tokens), 6 dp."""
    if provider == "mock":
        return 0.0
    price = MODEL_PRICING_USD_PER_1M.get(model)
    if price is None:
        return 0.0
    return round(input_tokens / 1e6 * price["input"] + output_tokens / 1e6 * price["output"], 6)


def cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class ResponseCache:
    def __init__(self, directory: Path):
        self.directory = directory

    def get(self, key: str) -> dict | None:
        path = self.directory / f"{key}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, key: str, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.directory / f"{key}.json.tmp"
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.directory / f"{key}.json")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _lock, path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
