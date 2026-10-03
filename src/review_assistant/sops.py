"""SOP registry. Each SOP gets a stable ID and a content-hash version for audit records."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .models import PolicyRef, Sop, SopSection

SOPS_RELATIVE_PATH = Path("policies_sops") / "sops.json"


def _sop_version(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


@lru_cache(maxsize=4)
def _load_sops_cached(data_dir: Path, mtime: float) -> dict[str, Sop]:
    path = data_dir / SOPS_RELATIVE_PATH
    entries = json.loads(path.read_text(encoding="utf-8"))
    registry: dict[str, Sop] = {}
    for entry in entries:
        sop_id = entry["sop_id"]
        version_payload = {
            "sop_id": entry["sop_id"],
            "title": entry["title"],
            "sections": entry["sections"],
        }
        registry[sop_id] = Sop(
            sop_id=sop_id,
            title=entry["title"],
            file=SOPS_RELATIVE_PATH.as_posix(),
            version=_sop_version(version_payload),
            sections=[SopSection(heading=s["heading"], text=s["text"]) for s in entry["sections"]],
        )
    return registry


def load_sops(data_dir: Path) -> dict[str, Sop]:
    path = data_dir / SOPS_RELATIVE_PATH
    return _load_sops_cached(data_dir, path.stat().st_mtime)


class SopRegistry:
    def __init__(self, data_dir: Path):
        self.sops = load_sops(data_dir)

    def ref(self, sop_id: str, section: str) -> PolicyRef:
        sop = self.sops[sop_id]
        sec = next((s for s in sop.sections if s.heading.lower() == section.lower()), None)
        if sec is None:
            raise KeyError(f"{sop_id} has no section '{section}'")
        return PolicyRef(sop_id=sop_id, title=sop.title, section=sec.heading, version=sop.version, excerpt=sec.text)

    def versions(self) -> dict[str, str]:
        return {k: v.version for k, v in self.sops.items()}

    def text(self, sop_id: str) -> str:
        return self.sops[sop_id].full_text()
