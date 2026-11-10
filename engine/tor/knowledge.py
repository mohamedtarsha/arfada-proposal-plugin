"""ARFADA Knowledge layer — deterministic verified-fact access (Phase 4).

Loads the plugin-local knowledge snapshot (knowledge/*.json) and exposes:
- fact lookup by fact_id (metrics, profile, capabilities)
- numeric authority (organizational totals come from here, never recomputed)
- relevant-experience retrieval (structured project metadata, no prose)
- knowledge_version + provenance

Every fact carries provenance. Nothing is invented: a missing fact returns None
so generation falls back to a NEEDS_ARFADA_EVIDENCE placeholder.

No network, no DB, no production dependency. Snapshot is versioned in Git.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _load(name: str) -> dict:
    path = _KNOWLEDGE_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def knowledge_version() -> str:
    vf = _KNOWLEDGE_DIR / "KNOWLEDGE_VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return "unknown"


class Knowledge:
    """In-memory view over the knowledge snapshot. Cheap to construct."""

    def __init__(self):
        self.version = knowledge_version()
        self._profile = _load("arfada_profile.json")
        self._metrics = _load("arfada_metrics.json")
        self._projects = _load("arfada_projects.json")
        self._provenance = _load("provenance.json")
        self._by_id: dict[str, dict] = {}
        self._index()

    def _index(self) -> None:
        # metrics
        for m in self._metrics.get("metrics", []):
            self._by_id[m["fact_id"]] = {**m, "kind": "metric"}
        # profile org + capabilities
        org = self._profile.get("organization")
        if org:
            self._by_id[org["fact_id"]] = {**org, "kind": "profile"}
        for c in self._profile.get("capabilities", []):
            self._by_id[c["fact_id"]] = {**c, "kind": "capability"}
        # projects
        for p in self._projects.get("projects", []):
            self._by_id[p["fact_id"]] = {**p, "kind": "project"}

    # --- fact access -------------------------------------------------------

    def fact(self, fact_id: str) -> Optional[dict]:
        """Return a verified fact by id, with provenance, or None if absent."""
        f = self._by_id.get(fact_id)
        if f is None:
            return None
        return {**f, "knowledge_version": self.version}

    def all_fact_ids(self) -> list[str]:
        return list(self._by_id.keys())

    # --- numeric authority -------------------------------------------------

    def metric(self, metric_name: str) -> Optional[dict]:
        """Deterministic numeric lookup by metric name (e.g. 'total_kii')."""
        for m in self._metrics.get("metrics", []):
            if m.get("metric") == metric_name:
                return {**m, "knowledge_version": self.version}
        return None

    def metrics(self) -> list[dict]:
        return [{**m, "knowledge_version": self.version}
                for m in self._metrics.get("metrics", [])]

    # --- relevant experience ----------------------------------------------

    def relevant_projects(
        self,
        *,
        assignment_type: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Evidence-based project selection — scored by metadata match only.

        Never claims similarity unsupported by metadata. Returns structured
        records (no prose). Empty list if nothing matches well.
        """
        scored: list[tuple[int, dict]] = []
        for p in self._projects.get("projects", []):
            score = 0
            if assignment_type and p.get("assignment_type") == assignment_type:
                score += 4
            if country and p.get("country", "").lower() == (country or "").lower():
                score += 3
            if region and p.get("region", "").lower() == (region or "").lower():
                score += 2
            if sector and sector.lower() in (p.get("sector", "").lower()):
                score += 2
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, p in scored[:limit]:
            out.append({**p, "match_score": score, "knowledge_version": self.version})
        return out

    # --- verified fact manifest for a generation packet -------------------

    def facts_for_section(self, section_id: str, *, assignment_type: str = "",
                          country: str = "", region: str = "MENA") -> list[dict]:
        """Return the verified facts relevant to a section (for packet injection).

        CONTEXT/UNDERSTANDING/EXECUTIVE_SUMMARY → aggregate metrics + org profile.
        EXPERIENCE → relevant projects. Others → org profile only.
        All facts carry provenance; generation may state ONLY these.
        """
        facts: list[dict] = []
        org = self.fact("org_name")
        if org:
            facts.append(_pack(org))

        if section_id in ("CONTEXT", "UNDERSTANDING", "EXECUTIVE_SUMMARY"):
            for m in self.metrics():
                facts.append(_pack(m))
        if section_id in ("EXPERIENCE",):
            for m in self.metrics():
                facts.append(_pack(m))
            for p in self.relevant_projects(assignment_type=assignment_type,
                                            country=country, region=region, limit=5):
                facts.append(_pack(p))
        return facts


def _pack(f: dict) -> dict:
    """Minimal fact descriptor for a generation packet."""
    label = f.get("label") or f.get("name") or f.get("metric") or f.get("client") or ""
    if f.get("kind") == "project":
        value = (f"{f.get('assignment_type', '')} for {f.get('client', '')} "
                 f"({f.get('country', '')}, {f.get('sector', '')}, {f.get('year', '')})")
    elif f.get("kind") == "metric":
        value = f"{f.get('value')} {f.get('unit', '')}".strip()
    else:
        value = f.get("value") or f.get("description") or ""
    return {
        "fact_id": f["fact_id"],
        "label": label,
        "value": value,
        "source": f.get("source", ""),
        "knowledge_version": f.get("knowledge_version", ""),
        "verified": f.get("verified", False),
    }
