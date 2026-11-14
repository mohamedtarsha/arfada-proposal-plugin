"""export_final.py — gated final client deliverable (v0.6.0).

Usage:
    python scripts/export_final.py <run_dir>            # export if GREEN
    python scripts/export_final.py <run_dir> --confirm  # export on YELLOW too

Gating (spec §34):
  GREEN  → produce proposal_final.docx
  YELLOW → requires --confirm
  RED    → blocked (exit 20); no client deliverable produced

Re-runs Final QA first so the gate reflects the current artifacts (no stale GREEN).
proposal_final.docx is the validated client content — no new content is introduced.
No model call, no network.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.final_qa import run_final_qa, to_markdown
from engine.tor.version import plugin_version

# Patterns that must NEVER survive into the final client deliverable (§8/§10).
_FORBIDDEN = (
    "[To be provided", "[TBD", "[PLACEHOLDER", "NEEDS_ARFADA_EVIDENCE",
    "BLOCKED_BY_DECISION", "Master Tracker", "master_tracker", "knowledge snapshot",
    "knowledge_snapshot", "STATIC_FALLBACK", "LOCAL_FOLDER", "GOOGLE_API",
    ".arfada-proposal", "fact_id", "req_", "slot_", "snap_",
)
_DRAFT_STAMP = "DRAFT — HUMAN REVIEW REQUIRED"


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(d, code=1):
    sys.stderr.buffer.write((json.dumps(d if isinstance(d, dict) else {"error": d},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def _load_docx(path):
    deps = _PLUGIN_ROOT / ".mcp_deps"
    if deps.exists() and str(deps) not in sys.path:
        sys.path.insert(0, str(deps))
    from docx import Document
    return Document(str(path))


def _doc_text(doc) -> str:
    text = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                text += "\n" + c.text
    return text


def _delete_paragraph(p):
    el = p._element
    el.getparent().remove(el)
    p._p = p._element = None


def sanitize_final(path, *, keep_draft_stamp: bool) -> dict:
    """Sanitize the final DOCX in place. Returns {ok, removed, leaks}.

    - GREEN (keep_draft_stamp=False): remove the DRAFT/HUMAN-REVIEW stamp.
    - Confirmed YELLOW (keep_draft_stamp=True): retain the stamp.
    - Always: strip '[To be provided: ...]' lines; then verify NO forbidden marker
      or internal/knowledge/tracker leakage remains.
    """
    doc = _load_docx(path)
    removed = []
    for p in list(doc.paragraphs):
        txt = p.text or ""
        if (not keep_draft_stamp) and _DRAFT_STAMP in txt:
            _delete_paragraph(p)
            removed.append("draft_stamp")
            continue
        if "[To be provided" in txt or "[TBD" in txt or "[PLACEHOLDER" in txt:
            _delete_paragraph(p)
            removed.append("placeholder")
    doc.save(str(path))

    # re-read and verify nothing forbidden remains
    check = _load_docx(path)
    text = _doc_text(check)
    if keep_draft_stamp:
        leaks = [m for m in _FORBIDDEN if m in text]
    else:
        leaks = [m for m in _FORBIDDEN if m in text] + (
            [_DRAFT_STAMP] if _DRAFT_STAMP in text else [])
    return {"ok": not leaks, "removed": removed, "leaks": leaks}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: export_final.py <run_dir> [--confirm]")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")
    confirm = "--confirm" in args

    # re-run QA (no stale GREEN)
    report = run_final_qa(run_dir, plugin_version=plugin_version())
    (run_dir / "final_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "final_qa.md").write_text(to_markdown(report), encoding="utf-8")
    status = report["overall_status"]

    if status == "RED":
        _err({"status": "BLOCKED", "overall_status": "RED",
              "reason": "Final export blocked by critical QA failures.",
              "critical": [f["message"] for f in report["critical_failures"]][:10]}, 20)
    if status == "YELLOW" and not confirm:
        _err({"status": "CONFIRMATION_REQUIRED", "overall_status": "YELLOW",
              "message": "QA has warnings. Re-run with --confirm to export the final despite them.",
              "warnings": [f["message"] for f in report["warnings"]][:10]}, 10)

    # produce proposal_final.docx from the validated client draft (no new content).
    client = run_dir / "proposal_client_draft.docx"
    if not client.exists():
        _err({"status": "NO_CLIENT_DRAFT",
              "message": "proposal_client_draft.docx not found — run render_docx.py --client first."}, 2)
    final = run_dir / "proposal_final.docx"
    shutil.copyfile(client, final)

    # Final sanitization (§10): GREEN drops the DRAFT stamp; confirmed YELLOW keeps
    # it. Either way, no '[To be provided]' / internal / knowledge-tracker leakage may
    # survive. On failure: delete the final and report FINAL_SANITIZE_FAILED.
    keep_draft = (status == "YELLOW")
    try:
        san = sanitize_final(final, keep_draft_stamp=keep_draft)
    except Exception as exc:  # python-docx missing or unreadable → do not ship a final
        if final.exists():
            final.unlink()
        _err({"status": "FINAL_SANITIZE_FAILED", "overall_status": status,
              "message": f"Could not sanitize the final deliverable: {exc}. "
                         "No final was produced."}, 30)
    if not san["ok"]:
        if final.exists():
            final.unlink()
        _err({"status": "FINAL_SANITIZE_FAILED", "overall_status": status,
              "leaks": san["leaks"],
              "message": "Final deliverable still contained forbidden internal/placeholder "
                         "content after sanitization. The final was deleted."}, 30)

    _out({
        "status": "EXPORTED",
        "overall_status": status,
        "confirmed": confirm,
        "plugin_version": plugin_version(),
        "draft_stamp_retained": keep_draft,
        "sanitized_removed": san["removed"],
        "proposal_final": "proposal_final.docx",
        "note": "Final = validated, sanitized client content. GREEN/confirmed-YELLOW only. "
                "Automated QA does not replace human review before submission.",
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
