"""Submission package check (v0.6.4, production hardening §11).

Verifies the ACTUAL files that make up the submission package exist on disk —
never trusts a textual claim like "CVs annexed" as proof. Run it before final
export (or right after GREEN QA) so the team sees exactly what is present and what
is still missing:

    proposal_final.docx · required CVs · previous-work example ·
    financial offer / detailed budget · any other TOR-required annex.

Annex files are discovered under the run directory and an optional `annexes/`
folder (with `cvs/`, `previous_work/`, `budget/` subfolders). Deterministic, no
network, no model call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

_DOC_EXT = (".pdf", ".docx", ".doc", ".xlsx", ".xls")


def _list_files(d: Path) -> list[str]:
    if not d.exists() or not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_file() and not f.name.startswith("~$")
                  and f.suffix.lower() in _DOC_EXT)


def _find(run_dir: Path, *names: str) -> Optional[str]:
    for n in names:
        p = run_dir / n
        if p.exists() and p.is_file():
            return n
    return None


def _glob_annex(run_dir: Path, sub: str) -> list[str]:
    """Files under annexes/<sub>/ or <sub>/ at the run root."""
    found = []
    found += [f"annexes/{sub}/{n}" for n in _list_files(run_dir / "annexes" / sub)]
    found += [f"{sub}/{n}" for n in _list_files(run_dir / sub)]
    return found


def check_submission_package(
    run_dir: str | Path, *,
    item_keys: Optional[list] = None,
    require_proposal: bool = True,
    min_cvs: int = 0,
) -> dict:
    """Verify physical submission artifacts.

    item_keys: submission checklist item_keys that imply a physical annex
    (e.g. 'cv_annex', 'previous_work', 'detailed_budget'). Presence is checked on
    disk; a missing file is reported by its real identity, not a generic label.
    """
    run_dir = Path(run_dir)
    items: list[dict] = []
    keys = set(item_keys or [])

    def add(label, present, files, hint=""):
        items.append({"label": label, "present": bool(present),
                      "files": files, "hint": hint})

    if require_proposal:
        pf = _find(run_dir, "proposal_final.docx")
        draft = _find(run_dir, "proposal_client_draft.docx")
        add("proposal_final.docx", bool(pf), [pf] if pf else [],
            hint="" if pf else ("client draft exists — run export_final to produce the final"
                                if draft else "render the client draft, then export the final"))

    if "cv_annex" in keys or min_cvs > 0:
        cvs = _glob_annex(run_dir, "cvs")
        add("Required CVs", len(cvs) >= max(min_cvs, 1), cvs,
            hint="" if cvs else "place team CV files under annexes/cvs/")

    if "previous_work" in keys:
        pw = _glob_annex(run_dir, "previous_work")
        # also honor a registered pointer
        reg = run_dir / "previous_work.json"
        if reg.exists():
            try:
                import json
                data = json.loads(reg.read_text(encoding="utf-8"))
                f = data.get("file")
                if f and Path(f).exists():
                    pw = pw or [f]
            except Exception:
                pass
        add("Previous-work example", bool(pw), pw,
            hint="" if pw else "validate + place the previous-work file (see previous_work.py)")

    if "detailed_budget" in keys:
        bf = _find(run_dir, "financial_offer.xlsx", "financial_offer.docx",
                   "detailed_budget.xlsx", "detailed_budget.docx")
        annex = _glob_annex(run_dir, "budget")
        files = ([bf] if bf else []) + annex
        add("Financial offer / detailed budget", bool(files), files,
            hint="" if files else "export the reconciled budget as a file in the package")

    # any other annex the checklist named (registration, tax, insurance, signature…)
    other = [k for k in keys if k not in
             ("cv_annex", "previous_work", "detailed_budget",
              "cover_letter", "technical_proposal", "methodology", "work_plan")]
    for k in other:
        annex = _glob_annex(run_dir, k)
        add(f"Annex: {k}", bool(annex), annex,
            hint="" if annex else f"place the {k} file under annexes/{k}/")

    missing = [it["label"] for it in items if not it["present"]]
    return {
        "run_dir": str(run_dir),
        "complete": not missing,
        "items": items,
        "missing": missing,
    }
