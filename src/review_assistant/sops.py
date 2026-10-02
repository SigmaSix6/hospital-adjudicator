"""SOP registry. Each SOP gets a stable ID and a content-hash version for audit records."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .ingestion import parse_docx, sha256_file
from .models import PolicyRef, Sop, SopSection


@lru_cache(maxsize=4)
def load_sops(data_dir: Path) -> dict[str, Sop]:
    registry: dict[str, Sop] = {}
    for path in sorted((data_dir / "policies_sops").glob("SOP-*.docx")):
        match = re.match(r"(SOP-\d+)", path.name)
        if not match:
            continue
        sop_id = match.group(1)
        title, _, sections = parse_docx(path)
        registry[sop_id] = Sop(
            sop_id=sop_id,
            title=title.removeprefix(sop_id).strip(),
            file=str(path.relative_to(data_dir)),
            version=f"sha256:{sha256_file(path)[:12]}",
            sections=[SopSection(heading=s.name, text=s.value) for s in sections],
        )
    return registry


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
