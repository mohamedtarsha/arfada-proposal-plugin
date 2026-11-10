"""render_docx.py — professional Word export (Phase 4).

Usage:
    python scripts/render_docx.py <run_dir> --internal
    python scripts/render_docx.py <run_dir> --client   [--logo <path>]

Runs a pre-export quality check, then renders proposal_internal_review.docx or
proposal_client_draft.docx from validated section JSON. Client export fails if a
hard unsupported-fact error is present. No MS Word automation, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.preexport_qa import preexport_check
from engine.tor.docx_render import render_docx


def _out(data: dict) -> None:
    s = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _err(msg, code: int = 1) -> None:
    sys.stderr.buffer.write((json.dumps(msg if isinstance(msg, dict) else {"error": msg},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: render_docx.py <run_dir> --internal|--client [--logo <path>]")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")

    internal = "--internal" in args
    client = "--client" in args
    if internal == client:
        _err("Specify exactly one of --internal or --client")
    logo = None
    if "--logo" in args:
        i = args.index("--logo")
        if i + 1 < len(args):
            logo = args[i + 1]
    # auto-resolve brand logo from the live Google cache if not supplied (spec §15).
    if not logo:
        try:
            from engine.tor.gknowledge.cache import Cache
            brand = Cache().brand()
            if brand and brand.get("available") and brand.get("logo_path"):
                lp = Path(brand["logo_path"])
                if lp.exists():
                    logo = str(lp)
        except Exception:
            logo = None  # fall back to neutral cover — never block export

    # pre-export QA
    qa = preexport_check(run_dir)
    if client and not qa["client_safe"]:
        _err({"status": "BLOCKED", "reason": "client export blocked by pre-export QA",
              "errors": qa["errors"]}, 5)
    if not qa["ok"] and not qa["client_safe"] and internal:
        # internal export proceeds even with warnings, but hard errors block it too
        hard = [e for e in qa["errors"] if "missing" in e or "FAILED" in e or "no READY" in e]
        if hard:
            _err({"status": "BLOCKED", "reason": "internal export blocked", "errors": hard}, 5)

    blueprint = _read_json(run_dir / "proposal_blueprint.json")
    status_doc = _read_json(run_dir / "generation_status.json")
    tor = _read_json(run_dir / "tor_analysis.json")
    blueprint["plugin_version"] = "0.5.0"

    try:
        result = render_docx(run_dir=run_dir, blueprint=blueprint, status_doc=status_doc,
                             tor=tor, internal=internal, logo_path=logo)
    except ValueError as e:
        _err({"status": "BLOCKED", "reason": str(e)}, 5)

    result["qa"] = {"ok": qa["ok"], "client_safe": qa["client_safe"],
                    "warnings": qa["warnings"], "errors": qa["errors"]}
    _out(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
