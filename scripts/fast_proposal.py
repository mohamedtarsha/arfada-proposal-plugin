"""fast_proposal.py — Fast Proposal Mode orchestrator (v0.6.5).

TOR → useful Word draft as fast as possible, with as few questions as possible.
Workflow only — the evidence/provenance/QA/knowledge/validation engines are unchanged.

Subcommands:
    setup <run_dir>        Auto-recommend every decision (PROVISIONAL), rank team +
                           experience, emit <=5 questions and a compact Proposed Setup,
                           persist provisional decisions, and build the blueprint.
    status <run_dir>       Two-status QA (TECHNICAL_DRAFT vs SUBMISSION_PACKAGE) and
                           write internal_gaps.md.
    gaps <run_dir>         (Re)write internal_gaps.md only.
    next-version <run_dir> Bump the working-draft version (draft_state.json) for v2, v3…

The session still authors section prose (no API); this script does everything around
it so the first DOCX arrives fast. Draft v1 is rendered with:
    render_docx.py <run_dir> --draft
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(d, code=1):
    sys.stderr.buffer.write((json.dumps(d if isinstance(d, dict) else {"error": d},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def _read(run_dir: Path, name: str, default=None):
    p = run_dir / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_setup(args) -> int:
    if not args:
        _err("Usage: fast_proposal.py setup <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}", 2)

    tor = _read(run_dir, "tor_analysis.json", {})
    requirements = (_read(run_dir, "requirements.json", {}) or {}).get("requirements", [])
    candidates = (_read(run_dir, "decision_candidates.json", {}) or {}).get("candidates", [])
    if not tor:
        _err({"status": "DRAFT_BLOCKER",
              "message": "No tor_analysis.json — run analyze_tor.py first."}, 3)

    from engine.tor import autopilot
    from engine.tor.knowledge import Knowledge
    try:
        knowledge = Knowledge(run_dir=run_dir)
    except Exception:
        knowledge = None

    result = autopilot.autopilot(tor, requirements, candidates, knowledge)

    # Writing DNA (mandatory writing layer) — persisted across sessions, auto-loaded.
    dna_summary = {"writing_dna_active": False, "historical_pairs": 0,
                   "relevant_proposals_retrieved": 0}
    try:
        from engine.tor.exemplars import retrieval as _ex

        def _mv(k):
            e = tor.get("metadata", {}).get(k)
            return (e.get("value", "") if isinstance(e, dict) else "").strip()
        at = tor.get("assignment_type", {})
        dna_summary = _ex.retrieval_summary(
            assignment_type=at.get("assignment_type") or "",
            country=_mv("country"), sector=_mv("sector"),
            evaluation_type=at.get("assignment_type") or "",
            thematic=_mv("assignment") or _mv("title"))
    except Exception:
        pass

    # persist provisional decisions into the register (init if needed)
    from engine.tor.register import (init_register, load_register, save_register,
                                     provisional_recommend)
    try:
        reg = load_register(run_dir)
    except Exception:
        reg = init_register(run_dir)
    applied, skipped = 0, []
    reg_ids = {d.decision_id for d in reg.decisions}
    for rec in result["recommendations"]:
        if rec["decision_id"] not in reg_ids:
            continue  # only human decisions live in the register
        r = provisional_recommend(reg, rec["decision_id"], rec["value"],
                                  rationale=rec["rationale"])
        if r["valid"]:
            applied += 1
        else:
            skipped.append({"decision_id": rec["decision_id"], "reason": r["message"]})
    save_register(reg, run_dir)

    # write artifacts
    (run_dir / "proposed_setup.json").write_text(
        json.dumps(result["proposed_setup"], ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "fast_questions.json").write_text(
        json.dumps(result["questions"], ensure_ascii=False, indent=2), encoding="utf-8")

    # build the blueprint using the provisional register
    blueprint_status = "built"
    try:
        from scripts.build_blueprint import main as build_main
        build_main([str(run_dir)])
    except SystemExit:
        pass
    except Exception as exc:
        blueprint_status = f"not built: {exc}"

    _out({
        "status": "SETUP_READY",
        "run_id": run_dir.name,
        "provisional_decisions_applied": applied,
        "skipped": skipped,
        "question_count": result["question_count"],
        "questions": result["questions"],
        "team_needs_question": result["team"].get("team_needs_question"),
        "staff_pool": {"searchable_profiles": result["team"].get("searchable_profiles", 0),
                       "source": result["team"].get("staff_pool_source", "")},
        "proposed_setup": result["proposed_setup"],
        "writing_dna": {
            "active": dna_summary.get("writing_dna_active"),
            "historical_pairs": dna_summary.get("historical_pairs"),
            "relevant_proposals_retrieved": dna_summary.get("relevant_proposals_retrieved"),
            "relevant_proposals": dna_summary.get("relevant_proposals", []),
        },
        "blueprint": blueprint_status,
        "next": "Answer up to 5 questions if any, then generate sections (Writing DNA "
                "active), render_docx.py <run_dir> --draft → proposal_draft_v1.docx, "
                "then fast_proposal.py style <run_dir> for the Writing-DNA style QA.",
    })
    return 0


def cmd_style(args) -> int:
    if not args:
        _err("Usage: fast_proposal.py style <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    from engine.tor.style_qa import style_qa_report
    report = style_qa_report(run_dir)
    (run_dir / "style_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _out(report)
    return 0


def cmd_status(args) -> int:
    if not args:
        _err("Usage: fast_proposal.py status <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    from engine.tor.fast_qa import two_status_report
    from engine.tor.package import check_submission_package
    from engine.tor.submission import build_submission_checklist

    extra = []
    reqs = (_read(run_dir, "requirements.json", {}) or {}).get("requirements", [])
    if reqs:
        # v0.6.12: only items that need their OWN file (CVs, previous work, budget,
        # registration, or an explicitly requested separate document) — never a
        # generic "Annex: other" for content items, deadlines or channels
        from engine.tor.submission import physical_annex_keys
        from engine.tor.submission_blockers import required_items
        item_keys = sorted(set(physical_annex_keys(reqs)) | set(required_items(reqs)))
        pkg = check_submission_package(run_dir, item_keys=item_keys)
        for miss in pkg["missing"]:
            extra.append({"message": f"Package item missing: {miss}",
                          "recommended_action": "Add the physical file to the package."})

    report = two_status_report(run_dir, extra_submission_gaps=extra)
    (run_dir / "internal_gaps.md").write_text(report["internal_gaps_md"], encoding="utf-8")
    report["internal_gaps_file"] = "internal_gaps.md"
    _out(report)
    return 0


def cmd_gaps(args) -> int:
    if not args:
        _err("Usage: fast_proposal.py gaps <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    from engine.tor.fast_qa import two_status_report
    report = two_status_report(run_dir)
    (run_dir / "internal_gaps.md").write_text(report["internal_gaps_md"], encoding="utf-8")
    _out({"status": "ok", "internal_gaps_file": "internal_gaps.md",
          "summary_line": report["summary_line"]})
    return 0


def cmd_next_version(args) -> int:
    if not args:
        _err("Usage: fast_proposal.py next-version <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    ds = run_dir / "draft_state.json"
    version = 1
    if ds.exists():
        try:
            version = int(json.loads(ds.read_text()).get("version", 1)) + 1
        except Exception:
            version = 2
    ds.write_text(json.dumps({"version": version}), encoding="utf-8")
    _out({"status": "ok", "version": version,
          "next": f"render_docx.py <run_dir> --draft --version {version} "
                  f"→ proposal_draft_v{version}.docx"})
    return 0


_COMMANDS = {"setup": cmd_setup, "status": cmd_status, "gaps": cmd_gaps,
             "next-version": cmd_next_version, "style": cmd_style}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or args[0] not in _COMMANDS:
        _err(f"Usage: fast_proposal.py <{' | '.join(_COMMANDS)}> <run_dir>")
    return _COMMANDS[args[0]](args[1:])


if __name__ == "__main__":
    sys.exit(main())
