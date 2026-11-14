"""Run initialization summary (v0.6.4, production hardening §1).

At the start of every new TOR run, verify and report — in ONE compact summary —
the state of everything a proposal depends on, WITHOUT regenerating or re-indexing:

  ARFADA Knowledge source · Master Tracker · Staff CVs · Company documents ·
  Previous Work folder · Writing DNA · historical TOR↔Proposal pairs ·
  plugin version · knowledge snapshot version.

Writing DNA and the exemplar index persist across sessions under ARFADA_HOME, so a
fresh chat automatically discovers and loads them (no re-scan needed). Every probe
is best-effort: a missing subsystem reports INACTIVE rather than raising.
"""
from __future__ import annotations

from typing import Any

ACTIVE = "ACTIVE"
INACTIVE = "INACTIVE"
STATIC = "STATIC_FALLBACK"


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def gather_init_status() -> dict:
    """Collect the full initialization status dict (no side effects, no re-index)."""
    status: dict[str, Any] = {}

    # --- plugin version (authoritative) ---
    from .version import plugin_version
    status["plugin_version"] = plugin_version()

    # --- knowledge source + sub-sources ---
    knowledge_root = _safe(_knowledge_root)
    cache = _safe(_cache)
    source_mode = STATIC
    projects = staff = company = None
    if cache is not None and _safe(cache.has_any, False):
        origin = _safe(cache.source_mode) or "LOCAL_FOLDER"
        source_mode = origin
        projects = _safe(cache.projects)
        staff = _safe(cache.staff)
        company = _safe(cache.company)

    proj_count = (projects or {}).get("count", 0) if projects else 0
    staff_count = (staff or {}).get("count", 0) if staff else 0
    company_docs = len((company or {}).get("facts", [])) if company else 0

    status["knowledge"] = {
        "source_mode": source_mode,
        "state": ACTIVE if source_mode != STATIC else STATIC,
        "knowledge_root": knowledge_root,
        "last_refresh": _safe(cache.last_sync) if cache else None,
    }
    status["master_tracker"] = {
        "state": ACTIVE if proj_count else INACTIVE,
        "projects": proj_count,
    }
    status["staff_cvs"] = {
        "state": ACTIVE if staff_count else INACTIVE,
        "profiles": staff_count,
    }
    status["company_documents"] = {
        "state": ACTIVE if company_docs else INACTIVE,
        "documents": company_docs,
    }
    status["previous_work_library"] = _previous_work_status(knowledge_root)

    # --- Writing DNA + historical pairs (persisted across sessions) ---
    dna = _safe(_writing_dna, {}) or {}
    configured = bool(_safe(_exemplars_configured, False))
    pairs = _safe(_historical_pairs, 0) or 0
    status["writing_dna"] = {
        "state": ACTIVE if (configured and dna.get("documents")) else INACTIVE,
        "documents": dna.get("documents", 0),
        "persisted": True,  # lives under ARFADA_HOME; auto-discovered by a new session
    }
    status["historical_pairs"] = pairs

    # --- knowledge snapshot version ---
    status["knowledge_snapshot_version"] = _safe(_static_knowledge_version, "unknown")

    return status


def compact_summary(status: dict) -> str:
    """Render the compact human summary block (spec §1 example)."""
    def mark(s):
        return s if s in (ACTIVE, INACTIVE, STATIC) else (ACTIVE if s else INACTIVE)

    lines = [
        f"Knowledge: {mark(status['knowledge']['state'])}",
        f"Master Tracker: {mark(status['master_tracker']['state'])}",
        f"Staff CVs: {mark(status['staff_cvs']['state'])}",
        f"Company docs: {mark(status['company_documents']['state'])}",
        f"Writing DNA: {mark(status['writing_dna']['state'])}",
        f"Historical pairs: {status['historical_pairs']}",
        f"Previous Work library: {mark(status['previous_work_library']['state'])}",
        f"Plugin: v{status['plugin_version']} · "
        f"Knowledge snapshot: {status['knowledge_snapshot_version']}",
    ]
    return "\n".join(lines)


# --- probes (isolated so one failure never breaks the summary) ----------------

def _knowledge_root():
    from .lknowledge import local_config as LC
    return LC.get_knowledge_root()


def _cache():
    from .gknowledge.cache import Cache
    return Cache()


def _writing_dna():
    from .exemplars import retrieval
    return retrieval.writing_dna()


def _exemplars_configured():
    from .exemplars import retrieval
    return retrieval.is_configured()


def _historical_pairs():
    """Count TOR↔Proposal pairs from the persisted exemplar index."""
    from .exemplars.scan import exemplar_cache_dir, _load_index
    idx = _load_index(exemplar_cache_dir())
    return sum(1 for e in idx.get("exemplars", []) if e.get("tor_file"))


def _static_knowledge_version():
    from .knowledge import knowledge_version
    return knowledge_version()


def _previous_work_status(knowledge_root):
    """Previous Work = winning-proposal/exemplar library folder, if configured."""
    try:
        from .exemplars import exemplar_config as EC
        root = EC.get_library_root()
        return {"state": ACTIVE if root else INACTIVE, "library_root": root}
    except Exception:
        return {"state": INACTIVE, "library_root": None}
