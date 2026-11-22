"""Run-level user decisions that resolve submission blockers (v0.6.16).

Recorded only from an explicit user / employee decision (never inferred), with the
user's own words and a timestamp, in ``run_decisions.json``:

  run_purpose          LIVE_SUBMISSION | TEST_REPLAY
                       (asked when the TOR deadline has passed and it is not yet known)
  submission_channel   an e-mail address / platform name / URL the employee entered, or
                       NOT_KNOWN ("Not known yet" keeps the blocker)
  registration_choice  the registration document chosen when several were found
  team_availability    CONFIRMED_BY_USER for all currently selected experts (bulk) —
                       written per staff_profile_id to team_availability.json

Nothing here invents a fact: a channel must be a concrete value (placeholders such as
"[submission platform/email]" or "TBD" are rejected), and availability needs explicit
confirmation wording.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Optional

FILE = "run_decisions.json"
AVAILABILITY_FILE = "team_availability.json"

LIVE_SUBMISSION = "LIVE_SUBMISSION"
TEST_REPLAY = "TEST_REPLAY"
RUN_PURPOSES = (LIVE_SUBMISSION, TEST_REPLAY)
NOT_KNOWN = "NOT_KNOWN"
USER_CONFIRMED = "USER_CONFIRMED"
CONFIRMED_BY_USER = "CONFIRMED_BY_USER"

RUN_PURPOSE_QUESTION = "Is this a live submission or a test/replay of an older TOR?"
CHANNEL_QUESTION = ("Please enter the submission email or platform specified/confirmed for this "
                    "opportunity.")

_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_URL = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
_PLACEHOLDER = re.compile(r"[\[\]{}<>]|\b(?:tbd|tbc|n/?a|xxx+|unknown|placeholder|to\s+be\s+"
                          r"(?:confirmed|determined|advised))\b", re.I)
_NOT_KNOWN = re.compile(r"^\s*(?:not\s+known(?:\s+yet)?|unknown|don'?t\s+know|no\s+idea|"
                        r"not\s+yet\s+known|n/?a)\s*\.?\s*$", re.I)
_AVAILABLE = re.compile(r"\b(?:are|is|have\s+been|been|confirmed(?:\s+as)?|all)\b[^.]{0,40}\bavailable\b|"
                        r"\bavailability\b[^.]{0,30}\bconfirmed\b|\bconfirm(?:ed)?\b[^.]{0,40}\bavailab",
                        re.I)
_HEDGE = re.compile(r"\b(?:not|no|never|pending|check|ask|maybe|probably|if|whether|unless|"
                    r"should|might|unconfirmed|tentative|likely)\b|\?", re.I)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def load(run_dir) -> dict:
    p = Path(run_dir) / FILE
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _save(run_dir, doc: dict) -> None:
    (Path(run_dir) / FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                                      encoding="utf-8")


def get(run_dir, key: str) -> Optional[dict]:
    d = load(run_dir).get(key)
    return d if isinstance(d, dict) else None


def run_purpose(run_dir) -> str:
    d = get(run_dir, "run_purpose")
    return d.get("value", "") if d else ""


def normalise_channel(value: str) -> Optional[str]:
    """A concrete channel (e-mail / URL / platform name), NOT_KNOWN, or None (invalid)."""
    v = " ".join(str(value or "").split())
    if not v:
        return None
    if _NOT_KNOWN.match(v):
        return NOT_KNOWN
    if _PLACEHOLDER.search(v):
        return None
    if _EMAIL.match(v) or _URL.match(v):
        return v
    # a platform name: letters, a few words, no sentence ("via the portal" is not a channel)
    if 2 <= len(v) <= 80 and re.search(r"[A-Za-z]", v) and len(v.split()) <= 8 and \
            not re.fullmatch(r"(?i)(?:the\s+)?(?:portal|platform|e-?mail|website|online|system)", v):
        return v
    return None


def is_explicit_availability(note: Optional[str]) -> bool:
    """'All selected experts are available' — unhedged, explicit confirmation only."""
    return bool(note and _AVAILABLE.search(note) and not _HEDGE.search(note))


def record(run_dir, key: str, value: str, *, note: str = "") -> dict:
    """Record one decision; returns {ok, status, …}. Invalid input is refused."""
    run_dir = Path(run_dir)
    doc = load(run_dir)
    if key == "run_purpose":
        v = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        v = {"LIVE": LIVE_SUBMISSION, "TEST": TEST_REPLAY, "REPLAY": TEST_REPLAY}.get(v, v)
        if v not in RUN_PURPOSES:
            return {"ok": False, "status": "INVALID",
                    "message": "run_purpose must be LIVE_SUBMISSION or TEST_REPLAY."}
        doc["run_purpose"] = {"value": v, "source": USER_CONFIRMED, "note": note[:300],
                              "recorded_at": _now()}
    elif key == "submission_channel":
        v = normalise_channel(value)
        if v is None:
            return {"ok": False, "status": "INVALID",
                    "message": "Enter a concrete e-mail address, platform name or URL, or "
                               "'Not known yet'. Placeholders are not a channel."}
        doc["submission_channel"] = {"value": v, "source": USER_CONFIRMED if v != NOT_KNOWN
                                     else NOT_KNOWN, "note": note[:300], "recorded_at": _now()}
    elif key == "registration_choice":
        p = Path(str(value or ""))
        if not p.is_file():
            return {"ok": False, "status": "INVALID", "message": f"File not found: {value}"}
        doc["registration_choice"] = {"value": str(p), "source": USER_CONFIRMED,
                                      "note": note[:300], "recorded_at": _now()}
    elif key == "team_availability":
        return confirm_team_availability(run_dir, note or str(value or ""))
    else:
        return {"ok": False, "status": "UNKNOWN_KEY", "message": f"Unknown decision '{key}'."}
    _save(run_dir, doc)
    return {"ok": True, "status": "RECORDED", "key": key, "value": doc[key]["value"]}


def _team(run_dir: Path) -> list:
    try:
        setup = json.loads((run_dir / "proposed_setup.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    return [m for m in setup.get("team") or [] if isinstance(m, dict) and
            (m.get("staff_profile_id") or m.get("staff_id"))]


def confirm_team_availability(run_dir, note: str) -> dict:
    """Bulk: mark every CURRENTLY selected expert available — explicit wording only."""
    run_dir = Path(run_dir)
    if not is_explicit_availability(note):
        return {"ok": False, "status": "NOT_EXPLICIT",
                "message": "Availability needs the user's explicit confirmation, e.g. "
                           "'All selected experts are available'."}
    team = _team(run_dir)
    if not team:
        return {"ok": False, "status": "NO_TEAM", "message": "No experts are selected yet."}
    p = run_dir / AVAILABILITY_FILE
    try:
        avail = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        avail = {}
    ids = [str(m.get("staff_profile_id") or m.get("staff_id")) for m in team]
    for sid in ids:
        avail[sid] = True
    avail["_provenance"] = {"decision": CONFIRMED_BY_USER, "scope": "all selected experts",
                            "staff_profile_ids": ids, "note": note.strip()[:300],
                            "recorded_at": _now()}
    p.write_text(json.dumps(avail, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = load(run_dir)
    doc["team_availability"] = {"value": CONFIRMED_BY_USER, "staff_profile_ids": ids,
                                "note": note.strip()[:300], "recorded_at": _now()}
    _save(run_dir, doc)
    return {"ok": True, "status": "RECORDED", "key": "team_availability", "confirmed": ids}
