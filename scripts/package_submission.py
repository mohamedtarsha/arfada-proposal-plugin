"""package_submission.py — auto-package annexes that ARFADA Knowledge already holds (v0.6.16).

Usage:
    python scripts/package_submission.py <run_dir>

Copies each selected expert's ORIGINAL CV from ARFADA Knowledge/Staff CVs into
annexes/cvs/ (identity-checked; cv_package_manifest.json) and, when exactly one current
registration certificate exists in ARFADA Knowledge/Company (or the employee chose one),
copies it into annexes/registration/ (registration_provenance.json). Nothing is
rewritten or invented. `fast_proposal.py status` runs this automatically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.stderr.write(__doc__)
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    from engine.tor.package_builder import auto_package
    res = auto_package(run_dir)
    sys.stdout.buffer.write((json.dumps(res, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
