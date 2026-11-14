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
import re
from pathlib import Path
from typing import Any, Optional

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"

_STOP = {"the", "and", "for", "of", "in", "a", "an", "to", "on", "with", "project",
         "study", "evaluation", "assessment", "final", "report"}


def _tokens(text: str) -> set:
    """Lowercase alphanumeric tokens >2 chars, minus common stopwords."""
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
            if t not in _STOP}


def _matches_current(project: dict, current: dict) -> bool:
    """True if a project is the SAME as the current TOR/assignment (run-scoped drop).

    Conservative: requires a project-name match, OR a (country + assignment_type)
    match combined with meaningful name-token overlap. Never drops on country alone,
    so unrelated past work in the same country is still cited.
    """
    pname = (project.get("project_name") or "").strip().lower()
    cname = (current.get("project_name") or current.get("assignment") or "").strip().lower()
    if cname and pname and (cname == pname or cname in pname or pname in cname):
        return True
    cc = (current.get("country") or "").lower()
    ct = (current.get("assignment_type") or "").upper()
    if cc and ct and (project.get("country") or "").lower() == cc \
            and (project.get("assignment_type") or "").upper() == ct:
        # Require DISTINCTIVE name overlap — strip generic type/country words so two
        # unrelated "endline … Jordan" assignments are not treated as the same.
        generic = {"endline", "baseline", "midline", "survey", "review", "programme",
                   "program", "response", "phase"} | {t for t in _tokens(cc)}
        a = _tokens(cname) - generic
        b = _tokens(pname) - generic
        if a and b and (a & b):
            return True
    return False


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

    def __init__(self, run_dir=None):
        """Load ARFADA knowledge with source priority (spec §27):
        1. frozen run snapshot (if run_dir has one)
        2. latest validated live Google cache
        3. static Git snapshot fallback (STATIC_FALLBACK)
        """
        self.version = knowledge_version()
        self._profile = _load("arfada_profile.json")
        self._metrics = _load("arfada_metrics.json")
        self._projects = _load("arfada_projects.json")
        self._provenance = _load("provenance.json")
        self.source_mode = "STATIC_FALLBACK"
        self._live_projects: Optional[list] = None
        self._live_metrics: Optional[dict] = None
        self._live_staff: list = []
        self._resolve_source(run_dir)
        self._by_id: dict[str, dict] = {}
        self._index()

    def _resolve_source(self, run_dir) -> None:
        # 1. frozen snapshot on the run
        try:
            if run_dir is not None:
                from .gknowledge import snapshot as _snap
                from pathlib import Path as _P
                if _snap.snapshot_exists(_P(run_dir)):
                    manifest = _snap.load_manifest(_P(run_dir)) or {}
                    self.source_mode = manifest.get("source_mode", "STATIC_FALLBACK")
                    self._live_projects = _snap.snapshot_projects(_P(run_dir))
                    self._live_metrics = _snap.snapshot_metrics(_P(run_dir))
                    self._live_staff = _snap.snapshot_staff(_P(run_dir))
                    self.snapshot_manifest = manifest
                    return
        except Exception:
            pass
        # 2. live Google cache
        try:
            from .gknowledge.cache import Cache
            c = Cache()
            if c.has_any():
                pj = c.projects()
                if pj:
                    self._live_projects = pj.get("projects", [])
                    self._live_metrics = pj.get("metrics", {})
                sf = c.staff()
                if sf:
                    self._live_staff = sf.get("profiles", [])
                # origin recorded by the sync/scan (LOCAL_FOLDER | GOOGLE_API)
                self.source_mode = c.source_mode() or "LIVE_GOOGLE"
                return
        except Exception:
            pass
        # 3. static fallback (default)
        self.source_mode = "STATIC_FALLBACK"

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

    def _source_tag(self) -> dict:
        return {"source_mode": self.source_mode, "knowledge_version": self.version}

    def metric(self, metric_name: str) -> Optional[dict]:
        """Deterministic numeric lookup by metric name (e.g. 'total_kii').

        Prefers live/snapshot-computed metrics; falls back to the static snapshot.
        """
        if self._live_metrics and metric_name in self._live_metrics:
            lv = self._live_metrics[metric_name]
            return {"fact_id": f"metric_{metric_name}", "metric": metric_name,
                    "value": lv.get("value"), **self._source_tag(),
                    "source": self.source_mode, "verified": True}
        for m in self._metrics.get("metrics", []):
            if m.get("metric") == metric_name:
                return {**m, **self._source_tag()}
        return None

    def metrics(self) -> list[dict]:
        if self._live_metrics:
            out = []
            for name, lv in self._live_metrics.items():
                if name == "countries":
                    continue
                out.append({"fact_id": f"metric_{name}", "metric": name,
                            "label": name.replace("_", " ").title(),
                            "value": lv.get("value"), "source": self.source_mode,
                            "verified": True, **self._source_tag()})
            return out
        return [{**m, **self._source_tag()} for m in self._metrics.get("metrics", [])]

    # --- relevant experience ----------------------------------------------

    def _project_pool(self) -> list[dict]:
        if self._live_projects is not None:
            return self._live_projects
        return self._projects.get("projects", [])

    def relevant_projects(
        self,
        *,
        assignment_type: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        sectors: Optional[list] = None,
        client: Optional[str] = None,
        donor: Optional[str] = None,
        evaluation_type: Optional[str] = None,
        thematic: Optional[str] = None,
        exclude_project_ids: Optional[set] = None,
        exclude_current: Optional[dict] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Evidence-based past-experience ranking — scored by metadata match only.

        Ranks on country, assignment/evaluation type, sector(s), client/donor, and
        thematic token similarity. The CURRENT TOR/project is excluded run-scoped
        (exclude_project_ids / exclude_current) so a proposal never cites itself —
        this exclusion is retrieval-only and does NOT change global portfolio
        metrics (those come from compute_metrics over the full tracker).

        Uses the active source (snapshot > live > static). Returns structured
        records (no prose), each with a scored_on breakdown. Empty if no match.
        """
        want_sectors = [s.lower() for s in (sectors or []) if s]
        if sector:
            want_sectors.append(sector.lower())
        thematic_tokens = _tokens(thematic) if thematic else set()
        exclude_ids = {str(x) for x in (exclude_project_ids or set())}

        scored: list[tuple[int, dict, dict]] = []
        for p in self._project_pool():
            if str(p.get("project_id") or p.get("fact_id") or "") in exclude_ids:
                continue
            if exclude_current and _matches_current(p, exclude_current):
                continue
            score = 0
            why = {}
            if assignment_type and p.get("assignment_type") == assignment_type:
                score += 4; why["assignment_type"] = 4
            if evaluation_type and evaluation_type.lower() in (
                    (p.get("assignment_type") or "") + " " + (p.get("sector") or "")).lower():
                score += 2; why["evaluation_type"] = 2
            if country and (p.get("country") or "").lower() == (country or "").lower():
                score += 3; why["country"] = 3
            if region and (p.get("region") or "").lower() == (region or "").lower():
                score += 2; why["region"] = 2
            psec = (p.get("sector") or "").lower()
            if want_sectors and any(s in psec or psec in s for s in want_sectors if s):
                score += 2; why["sector"] = 2
            if client and client.lower() in (
                    (p.get("client") or "") + " " + (p.get("donor") or "")).lower():
                score += 3; why["client"] = 3
            if donor and donor.lower() in (
                    (p.get("donor") or "") + " " + (p.get("client") or "")).lower():
                score += 2; why["donor"] = 2
            if thematic_tokens:
                hay = _tokens(" ".join(str(p.get(k) or "") for k in
                                       ("project_name", "sector", "description")))
                overlap = len(thematic_tokens & hay)
                if overlap:
                    score += min(overlap, 3); why["thematic"] = min(overlap, 3)
            if score > 0:
                scored.append((score, p, why))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, p, why in scored[:limit]:
            fid = p.get("fact_id") or p.get("project_id") or "proj"
            out.append({**p, "fact_id": fid, "match_score": score,
                        "scored_on": why, **self._source_tag()})
        return out

    # --- staff matching (spec §13) ----------------------------------------

    def search_staff(
        self, *, country: Optional[str] = None, role: Optional[str] = None,
        min_years: Optional[int] = None, language: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Deterministic staff candidate search over normalized CV profiles.

        Hard constraints (min_years) FILTER; soft factors RANK. Never auto-selects
        — returns candidate suggestions for user approval via Decision Review.
        """
        candidates = []
        for p in self._live_staff:
            # hard filter: minimum years of experience
            if min_years is not None:
                ye = p.get("years_experience")
                if ye is None or ye < min_years:
                    continue
            score = 0
            if country and (p.get("country") or "").lower() == country.lower():
                score += 4
            if role and any(role.lower() in r.lower() for r in p.get("roles", [])):
                score += 3
            if language and any(language.lower() == l.lower() for l in p.get("languages", [])):
                score += 2
            candidates.append((score, p))
        candidates.sort(key=lambda x: -x[0])
        return [{**p, "match_score": s, "approved": False, **self._source_tag()}
                for s, p in candidates[:limit]]

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
                facts.append(_pack({**m, "kind": "metric"}, self.source_mode))
        if section_id in ("EXPERIENCE",):
            for m in self.metrics():
                facts.append(_pack({**m, "kind": "metric"}, self.source_mode))
            for p in self.relevant_projects(assignment_type=assignment_type,
                                            country=country, region=region, limit=5):
                facts.append(_pack({**p, "kind": "project"}, self.source_mode))
        return facts


def _pack(f: dict, source_mode: str = "") -> dict:
    """Minimal fact descriptor for a generation packet (works for static + live)."""
    label = (f.get("label") or f.get("name") or f.get("project_name")
             or f.get("metric") or f.get("client") or "")
    if f.get("kind") == "project":
        value = (f"{f.get('assignment_type', '')} for {f.get('client', '')} "
                 f"({f.get('country', '')}, {f.get('sector', '')})").replace(" ()", "")
    elif f.get("kind") == "metric":
        value = f"{f.get('value')} {f.get('unit', '')}".strip()
    else:
        value = f.get("value") or f.get("description") or ""
    return {
        "fact_id": f.get("fact_id") or f.get("project_id") or "fact",
        "label": label,
        "value": value,
        "source": source_mode or f.get("source", ""),
        "source_mode": source_mode or f.get("source_mode", ""),
        "knowledge_version": f.get("knowledge_version", ""),
        "verified": f.get("verified", False),
    }
