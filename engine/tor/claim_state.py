"""Canonical claim / evidence state for a proposal run (v0.6.11).

Every fact that can appear in proposal text is given one status:

  VERIFIED        evidenced in the run (file in the package, cleared record, CV text,
                  explicit TOR statement)
  PROVISIONAL     partly evidenced or pending a human confirmation
  UNVERIFIED      asserted nowhere / evidence ambiguous
  MISSING         required by the TOR (or by the process) and not yet available
  NOT_APPLICABLE  not required for this TOR

The state is built ONLY from the run's own artifacts (requirements, TOR metadata,
budget.json, previous_work.json, annexes/, proposed_setup.json, staff facts, the
persisted staff pool) and written to ``claim_state.json``. Generation, validation,
QA and export all read it, so no unresolved fact can be written as complete.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Optional

VERIFIED = "VERIFIED"
PROVISIONAL = "PROVISIONAL"
UNVERIFIED = "UNVERIFIED"
MISSING = "MISSING"
NOT_APPLICABLE = "NOT_APPLICABLE"
STATUSES = (VERIFIED, PROVISIONAL, UNVERIFIED, MISSING, NOT_APPLICABLE)

CLAIM_FILE = "claim_state.json"

# Allowed wording for a fact that is NOT verified (generation + sanitizer use these)
SAFE_WORDING = {
    "registration_evidence": "Registration evidence will be included in the final submission "
                             "package.",
    "financial_proposal": "A separate financial proposal will be included once rates and costs "
                          "are confirmed.",
    "previous_work_sample": "An example of previous work will be included in the final "
                            "submission package once sharing clearance is confirmed.",
    "previous_work_clearance": "The proposed example of previous work will be included in the "
                               "final submission package once permission to share it is "
                               "confirmed.",
    "team_cv_package": "CVs of the proposed team members will be included in the final "
                       "submission package.",
    "team_availability": "Availability of the proposed experts will be confirmed prior to final "
                         "submission.",
    "submission_channel": "The submission channel is pending confirmation with the client.",
    "deadline": "The submission deadline will be confirmed with the client.",
    "field_roster": "ARFADA will confirm or recruit a locally based field team prior to "
                    "mobilization.",
    "source_inconsistency": "Values reproduced from the TOR will be reconciled against the "
                            "approved baseline dataset and PMF during inception where "
                            "inconsistencies exist.",
    # v0.6.13: a stratum allocation derived from a TOR TARGET composition
    "target_allocation": "Provisional allocation based on the TOR target composition: "
                         "{allocation}. The allocation will be recalculated at inception from "
                         "the registration list.",
}

_PLACEHOLDER = re.compile(
    r"\[[^\]]{0,60}(?:platform|e-?mail|address|link|portal|channel|website|url)[^\]]{0,60}\]|"
    r"\b(?:tbd|tbc|to\s+be\s+(?:confirmed|determined|advised))\b|x{3,}", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://\S+|www\.\S+")
_NAMED_CHANNEL = re.compile(
    r"\b(?:via|through|on|using)\s+(?:the\s+)?([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3})\s+"
    r"(?:portal|platform|system|e-?tendering)", re.I)
_SUBMIT_CUE = re.compile(r"\bsubmi(?:t|ssion)|\bdeadline\b|\bclosing\s+date\b|\bapply\b", re.I)
_MONTHS = ("january february march april may june july august september october november "
           "december").split()
_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(m[:3] for m in _MONTHS) + r")[a-z]*\.?,?\s+(\d{4})\b"
    r"|\b(" + "|".join(m[:3] for m in _MONTHS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"
    r"|\b(\d{4})-(\d{2})-(\d{2})\b"
    r"|\b(\d{1,2})-(" + "|".join(m[:3] for m in _MONTHS) + r")[a-z]*-(\d{4})\b", re.I)
_AMBIGUOUS_TIME = re.compile(r"\b12[:.]00\s*(?:a\.?m\.?|midnight)\b|\bmidnight\b", re.I)


def _load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _files(run_dir: Path, sub: str) -> list:
    out = []
    for base in (run_dir / "annexes" / sub, run_dir / sub):
        if base.is_dir():
            out += [str(p) for p in base.iterdir() if p.is_file()]
    return out


def claim(status: str, detail: str = "", *, required: bool = True, **extra) -> dict:
    assert status in STATUSES, status
    return {"status": status, "detail": detail, "required": required, **extra}


# ---------------------------------------------------------------------------
# submission channel / deadline (from the TOR's own submission text)
# ---------------------------------------------------------------------------

def _submission_text(tor: dict, requirements: list) -> str:
    parts = list((tor or {}).get("submission_instructions") or [])
    meta = (tor or {}).get("metadata", {}) or {}
    for k in ("submission_requirements", "proposal_requirements", "timeline"):
        e = meta.get(k)
        if isinstance(e, dict) and e.get("value"):
            parts.append(e["value"])
    for r in requirements or []:
        t = r.get("text") or ""
        if r.get("category") in ("submission", "proposal_format") or _SUBMIT_CUE.search(t):
            parts.append(t)
    return "\n".join(parts)


def submission_channel_state(tor: dict, requirements: list) -> dict:
    text = _submission_text(tor, requirements)
    if not text.strip():
        return claim(UNVERIFIED, "the TOR gives no submission instructions")
    m = _PLACEHOLDER.search(text)
    if m:
        return claim(MISSING, f"the TOR leaves the channel as a placeholder: {m.group(0)}",
                     placeholder=m.group(0))
    for rx in (_EMAIL, _URL):
        m = rx.search(text)
        if m:
            return claim(VERIFIED, "channel stated in the TOR", value=m.group(0))
    m = _NAMED_CHANNEL.search(text)
    if m:
        return claim(VERIFIED, "channel stated in the TOR", value=m.group(0))
    return claim(UNVERIFIED, "the TOR does not state a submission channel")


def _parse_date(m) -> Optional[_dt.date]:
    g = m.groups()
    try:
        if g[0]:
            return _dt.date(int(g[2]), [x[:3] for x in _MONTHS].index(g[1][:3].lower()) + 1, int(g[0]))
        if g[3]:
            return _dt.date(int(g[5]), [x[:3] for x in _MONTHS].index(g[3][:3].lower()) + 1, int(g[4]))
        if g[9]:
            return _dt.date(int(g[11]), [x[:3] for x in _MONTHS].index(g[10][:3].lower()) + 1, int(g[9]))
        return _dt.date(int(g[6]), int(g[7]), int(g[8]))
    except Exception:
        return None


def deadline_state(tor: dict, requirements: list, *, today: Optional[_dt.date] = None) -> dict:
    text = _submission_text(tor, requirements)
    cue = re.search(r"deadline|closing\s+date|no\s+later\s+than|"
                    r"\b(?:submi\w+|send|sent|e-?mail(?:ed)?)\b[^\n]{0,160}?\b(?:by|before|until)\b"
                    r"(?=\s*\d|\s+(?:the\s+)?\d|\s+[A-Z][a-z]+\s+\d)", text, re.I)
    if not cue:
        return claim(NOT_APPLICABLE, "no submission deadline stated", required=False)
    window = text[max(0, cue.start() - 40):cue.end() + 200]
    m = _DATE.search(window)
    if not m:
        return claim(MISSING, "the TOR mentions a deadline but no date could be read")
    date = _parse_date(m)
    today = today or _dt.date.today()
    notes = []
    if _AMBIGUOUS_TIME.search(window):
        notes.append("the time (12:00 AM / midnight) is ambiguous")
    if date and date < today:
        notes.append("the date appears to have passed")
    if notes:
        return claim(PROVISIONAL, "; ".join(notes), value=m.group(0))
    return claim(VERIFIED, "deadline stated in the TOR", value=m.group(0))


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _required_checklist_keys(requirements: list) -> set:
    from .submission import build_submission_checklist, MANDATORY
    from .submission_blockers import required_items
    keys = set(required_items(requirements))
    for e in build_submission_checklist(requirements):
        if e["obligation"] == MANDATORY:
            keys.add(e["item_key"])
    for r in requirements or []:          # "the proposal must include … CVs"
        if r.get("category") == "proposal_format" and r.get("actor") != "CLIENT" and \
                re.search(r"\b(?:cvs?|curriculum\s+vit|resum[eé]s?)\b", r.get("text") or "", re.I):
            keys.add("cv_annex")
    return keys


def _sampling_provenance(run_dir: Path) -> dict:
    """Stored sample-size arithmetic of the current draft (n / (1 − r), v0.6.13)."""
    sec_dir = run_dir / "generated_sections"
    if not sec_dir.exists():
        return {}
    try:
        from .numeric_claims import sampling_provenance, is_historical_section
        texts = []
        from .final_qa import _section_text          # the same flattening QA uses
        for f in sec_dir.glob("*.json"):
            if is_historical_section(f.stem):
                continue
            texts.append(_section_text(json.loads(f.read_text(encoding="utf-8"))))
        return sampling_provenance("\n".join(texts))
    except Exception:
        return {}


def _team(run_dir: Path) -> list:
    setup = _load(run_dir / "proposed_setup.json") or {}
    team = setup.get("team") or []
    return [m for m in team if isinstance(m, dict) and (m.get("staff_id") or m.get("name"))]


def build_claim_state(run_dir: str | Path, *, knowledge=None,
                      today: Optional[_dt.date] = None) -> dict:
    """Compute the canonical claim state for a run (no network, no model)."""
    from .submission_blockers import budget_state, previous_work_state, registration_state
    run_dir = Path(run_dir)
    tor = _load(run_dir / "tor_analysis.json") or {}
    requirements = (_load(run_dir / "requirements.json") or {}).get("requirements", [])
    required = _required_checklist_keys(requirements)
    claims: dict = {}

    # registration evidence
    if "registration" in required:
        ok, why = registration_state(run_dir)
        claims["registration_evidence"] = claim(VERIFIED if ok else MISSING, why)
    else:
        ok, _ = registration_state(run_dir)
        claims["registration_evidence"] = claim(VERIFIED if ok else NOT_APPLICABLE,
                                                "not required by the TOR", required=False)
    # financial proposal
    ok, why = budget_state(run_dir)
    partial = (run_dir / "budget.json").exists() and not ok
    if "detailed_budget" in required:
        claims["financial_proposal"] = claim(VERIFIED if ok else (PROVISIONAL if partial else MISSING), why)
    else:
        claims["financial_proposal"] = claim(VERIFIED if ok else NOT_APPLICABLE, why, required=False)
    # previous-work sample: SELECTION and SHARING CLEARANCE are independent (v0.6.12)
    from .previous_work_state import previous_work_states
    pw = previous_work_states(run_dir)
    ok, why = previous_work_state(run_dir)
    req_pw = "previous_work" in required
    claims["previous_work_selected"] = claim(
        pw["selected"]["status"] if (req_pw or pw["selected"]["status"] == VERIFIED)
        else NOT_APPLICABLE, pw["selected"]["detail"], required=req_pw,
        file=pw["selected"].get("file", ""), label=pw["selected"].get("label", ""))
    claims["previous_work_clearance"] = claim(
        pw["clearance"]["status"] if (req_pw or pw["selected"]["status"] == VERIFIED)
        else NOT_APPLICABLE, pw["clearance"]["detail"], required=req_pw,
        evidence=pw["clearance"].get("evidence", ""))
    if req_pw:
        claims["previous_work_sample"] = claim(
            VERIFIED if ok else (PROVISIONAL if pw["selected"]["status"] == VERIFIED else MISSING),
            why)
    else:
        claims["previous_work_sample"] = claim(VERIFIED if ok else NOT_APPLICABLE, why,
                                               required=False)
    # team CV package — v0.6.16: per selected expert, from the auto-package manifest
    cvs = _files(run_dir, "cvs")
    from .package_builder import cv_package_state
    cvp = cv_package_state(run_dir) if _team(run_dir) else None
    if "cv_annex" in required:
        if cvp is not None:
            claims["team_cv_package"] = claim(VERIFIED if cvp["ok"] else MISSING, cvp["detail"],
                                              files=len(cvs), packaged=cvp["packaged"],
                                              team_size=cvp["team_size"],
                                              unresolved=cvp["unresolved"])
        else:
            claims["team_cv_package"] = claim(VERIFIED if cvs else MISSING,
                                              f"{len(cvs)} CV file(s) in annexes/cvs/",
                                              files=len(cvs))
    else:
        claims["team_cv_package"] = claim(VERIFIED if cvs else NOT_APPLICABLE,
                                          "not required by the TOR", required=False)
    # team availability: only an explicit user decision makes it VERIFIED (never assumed)
    team = _team(run_dir)
    avail = _load(run_dir / "team_availability.json") or {}
    facts = (_load(run_dir / "team_staff_facts.json") or {})
    facts = facts.get("facts", facts) if isinstance(facts, dict) else facts
    facts = facts if isinstance(facts, list) else []
    if team:
        confirmed = [m for m in team if avail.get(str(m.get("staff_profile_id") or m.get("staff_id"))) is True
                     or any(f.get("staff_id") == m.get("staff_id") and
                            "availab" in str(f.get("attribute", "")).lower()
                            and f.get("verified") for f in facts)]
        st = VERIFIED if len(confirmed) == len(team) else UNVERIFIED
        prov = avail.get("_provenance") if isinstance(avail.get("_provenance"), dict) else {}
        detail = f"{len(confirmed)}/{len(team)} proposed experts confirmed available"
        if prov.get("decision"):
            detail += f" ({prov['decision']}: \"{prov.get('note', '')[:80]}\")"
        claims["team_availability"] = claim(
            st, detail, confirmed=len(confirmed), team_size=len(team),
            source=prov.get("decision", ""))
    else:
        claims["team_availability"] = claim(NOT_APPLICABLE, "no team proposed yet", required=False)
    # submission channel + deadline (from the TOR, then the employee's decisions — v0.6.16)
    from . import run_decisions as _rd
    decisions = _rd.load(run_dir)
    claims["submission_channel"] = submission_channel_state(tor, requirements)
    ch = decisions.get("submission_channel") or {}
    if claims["submission_channel"]["status"] != VERIFIED and ch.get("value"):
        if ch["value"] == _rd.NOT_KNOWN:
            claims["submission_channel"]["detail"] += " (employee: not known yet)"
        else:
            claims["submission_channel"] = claim(VERIFIED, "submission channel confirmed by the "
                                                 "employee", value=ch["value"],
                                                 source=_rd.USER_CONFIRMED)
    claims["deadline"] = deadline_state(tor, requirements, today=today)
    purpose = (decisions.get("run_purpose") or {}).get("value", "")
    dl = claims["deadline"]
    passed = "passed" in dl.get("detail", "")
    if passed and purpose == _rd.TEST_REPLAY:
        # a replay of an older TOR: record the real deadline, warn, never imply an extension
        claims["deadline"] = claim(NOT_APPLICABLE, f"TEST_REPLAY — the original TOR deadline "
                                   f"({dl.get('value', '')}) has passed; recorded for reference "
                                   "only, no extension is implied", required=False,
                                   value=dl.get("value", ""), warning=True,
                                   run_purpose=_rd.TEST_REPLAY)
    elif passed and purpose == _rd.LIVE_SUBMISSION:
        claims["deadline"] = claim(MISSING, f"LIVE_SUBMISSION — the TOR deadline "
                                   f"({dl.get('value', '')}) has passed; a written extension / "
                                   "client confirmation is required before final submission",
                                   value=dl.get("value", ""), run_purpose=_rd.LIVE_SUBMISSION)

    # personnel + field roster (indexed CV evidence)
    meta = tor.get("metadata", {}) or {}
    country = (meta.get("country") or {}).get("value", "") if isinstance(meta.get("country"), dict) else ""
    places = list(((meta.get("subnational_location") or {}).get("values") or []))
    team_claims = []
    roster = {"status": UNVERIFIED, "detail": "no staff pool available"}
    try:
        if knowledge is None:
            from .knowledge import Knowledge
            knowledge = Knowledge(run_dir=run_dir)
        pool = list(getattr(knowledge, "_live_staff", []) or [])
        by_id = {p.get("staff_id"): p for p in pool}
        from .lknowledge.staff_evidence import profile_claims, field_roster_readiness
        from .lknowledge.staff_identity import canonical_identity
        from .requirement_evidence import member_topic_evidence
        profiles = [by_id.get(m.get("staff_profile_id") or m.get("staff_id"), {**m}) for m in team]
        # v0.6.13: qualification evidence is read from the selected experts' own CV text
        # (cached role-evidence snippets), never from job titles or proposal commitments
        need = [p for p in profiles if not p.get("role_evidence") and p.get("source_rel_path")]
        if need:
            try:
                from .lknowledge.staff_role_fit import attach_role_evidence
                attach_role_evidence(need, budget_s=30.0)
            except Exception:
                pass
        for m, p in zip(team, profiles):
            sid = m.get("staff_profile_id") or m.get("staff_id")
            ident = canonical_identity(p, staff_facts=facts)
            team_claims.append({"staff_id": sid, **ident,
                                "name": ident["canonical_name"] or m.get("name"),
                                "role": m.get("role", ""),
                                "claims": profile_claims(p, places=places, staff_facts=facts),
                                "qualification_evidence": member_topic_evidence(
                                    p, staff_facts=facts, places=places)})
        if country:
            r = field_roster_readiness(pool, country=country, places=places)
            roster = {**r, "detail": (f"{r['field_cvs_in_target_area']} field CVs evidenced in "
                                      f"the target area, {r['field_cvs_in_country']} in-country")}
    except Exception as e:                       # never fail a run on evidence lookup
        roster = {"status": UNVERIFIED, "detail": f"staff evidence unavailable: {e}"}
    claims["field_roster"] = {**roster, "required": False}

    # v0.6.13: evidence-aware requirement coverage (team level; commitments never
    # satisfy a qualification)
    from .requirement_evidence import evidence_matrix
    company = {"field_roster": roster.get("status", UNVERIFIED),
               "field_roster_detail": roster.get("detail", "")}
    req_evidence = evidence_matrix(requirements, team_claims, places=places, company=company,
                                   claims=claims)
    # v0.6.13: source semantics of TOR population figures (TARGET is never promoted to
    # REGISTERED_CASELOAD) and the stored sample-size arithmetic
    from .source_semantics import load_register
    population = load_register(run_dir)

    inconsist = (_load(run_dir / "source_inconsistencies.json") or {}).get("items", [])
    return {"schema": "claim_state/1",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "claims": claims, "team": team_claims,
            "requirement_evidence": req_evidence,
            "run_purpose": (decisions.get("run_purpose") or {}).get("value", ""),
            "relevant_experience": _relevant_experience(run_dir),
            "places": places,
            "population_figures": population,
            "sampling_provenance": _sampling_provenance(run_dir),
            "source_inconsistencies": inconsist,
            # v0.6.12: duration wording exactly as the TOR writes it
            "tor_durations": list(tor.get("duration_mentions") or []),
            "safe_wording": SAFE_WORDING}


def _relevant_experience_policy(state: dict) -> dict:
    rx = state.get("relevant_experience") or {}
    if not rx:
        return {}
    from .relevant_experience import TABLE_COLUMNS, resolved
    if resolved(rx):
        return {"status": rx["status"], "table_columns": TABLE_COLUMNS,
                "assignments": [{k: c.get(k) for k in ("project_id", "project_name", "client",
                                                         "country", "year", "relevance")}
                                for c in rx["selected"]],
                "notes": rx.get("notes", []),
                "instruction": ("In the section that answers the TOR's relevant-experience "
                                "requirement, present exactly these Master Tracker assignments as a "
                                "table with table_columns (cite project_id in the ledger summary). "
                                "They are past assignments, separate from the previous-work report "
                                "offered as a sample. Never add other projects or a location the "
                                "tracker does not record.")}
    return {"status": rx.get("status"), "assignments": [], "notes": rx.get("notes", []),
            "instruction": ("Relevant-experience selection is unresolved: insert a "
                            "NEEDS_ARFADA_EVIDENCE placeholder for it (it is reported in "
                            "internal_gaps.md); never invent projects.")}


def _relevant_experience(run_dir: Path) -> dict:
    """v0.6.17: the selected Master Tracker assignments (separate from the work sample)."""
    try:
        from .relevant_experience import load
        doc = load(run_dir) or {}
    except Exception:
        doc = {}
    return {"status": doc.get("status", ""), "selected": doc.get("selected", []),
            "notes": doc.get("notes", []), "question": doc.get("question")} if doc else {}


def _qualification_rendering(state: dict) -> dict:
    try:
        from .qualification_wording import rendering_policy
        return rendering_policy(state)
    except Exception:
        return {}


def write_claim_state(run_dir: str | Path, **kw) -> dict:
    state = build_claim_state(run_dir, **kw)
    p = Path(run_dir) / CLAIM_FILE
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def generation_policy(state: dict) -> dict:
    """Compact claim policy for a generation packet: what may / may not be asserted."""
    rules = []
    for key, c in (state.get("claims") or {}).items():
        if c.get("status") in (VERIFIED, NOT_APPLICABLE):
            continue
        rules.append({"claim": key, "status": c.get("status"), "detail": c.get("detail", ""),
                      "do_not_state_as_complete": True,
                      "use_wording": SAFE_WORDING.get(key, "")})
    team = []
    for m in state.get("team") or []:
        verified = sorted(k for k, v in (m.get("claims") or {}).items() if v.get("status") == VERIFIED)
        unverified = sorted(k for k, v in (m.get("claims") or {}).items()
                            if v.get("status") in (UNVERIFIED, MISSING))
        team.append({"staff_profile_id": m.get("staff_profile_id") or m.get("staff_id"),
                     "canonical_name": m.get("canonical_name") or m.get("name"),
                     "canonical_name_status": m.get("canonical_name_status", ""),
                     "role": m.get("role", ""),
                     "name": m.get("canonical_name") or m.get("name"),
                     "verified_attributes": verified, "do_not_claim": unverified})
    return {"instruction": ("Write unresolved facts in provisional / future language only. "
                            "Never describe an item below as attached, provided, included, "
                            "confirmed, available, registered or submitted. Personnel: state "
                            "only VERIFIED attributes as qualifications, and always write each "
                            "member's full canonical_name (never initials); identify people "
                            "by staff_profile_id. If canonical_name_status is not VERIFIED, read "
                            "the CV and promote a full_name staff fact (staff_profile_id=…)."),
            "unresolved_claims": rules, "team": team,
            # v0.6.13: qualifications the selected team does not (fully) evidence — a
            # methodology commitment must not be written as the team's qualification
            "qualification_evidence_gaps": [
                {"req_id": r["req_id"], "requirement": r["text"][:160],
                 "evidence_status": r["evidence_status"], "not_evidenced": r["gaps"]}
                for r in state.get("requirement_evidence") or []
                if r.get("requirement_type") in ("PERSONNEL_QUALIFICATION", "COMPANY_QUALIFICATION")
                and r.get("evidence_status") not in ("VERIFIED", "NOT_REQUIRED")],
            "qualification_instruction": (
                "For a qualification listed in qualification_evidence_gaps, state only what the "
                "selected experts' CVs evidence; describe how the evaluation will apply the "
                "standard as a methodology commitment, never as the team's demonstrated "
                "qualification. Cite in the ledger every block that answers the requirement; "
                "QA computes the response from the text and the evidence separately, so weak "
                "evidence is not a reason to leave a requirement unanswered."
                ) if state.get("requirement_evidence") else "",
            "population_figures": [
                {"value": f["value"], "semantics": f["semantics"],
                 "registered_supported": f["registered_supported"], "label": f.get("label", "")}
                for f in (state.get("population_figures") or {}).get("figures", [])],
            "population_instruction": (
                "Never call a TARGET figure 'registered'. A stratum allocation derived from a TOR "
                "target composition is written as: " + SAFE_WORDING["target_allocation"])
            if (state.get("population_figures") or {}).get("figures") else "",
            # v0.6.15: client-facing qualification claims follow the evidence status
            "qualification_rendering": _qualification_rendering(state),
            # v0.6.17: relevant experience = tracker assignments, NOT the previous-work file
            "relevant_experience": _relevant_experience_policy(state),
            "sampling_rule": ("Non-response inflation: required initial sample = n / (1 - r) "
                              "(225 / 0.90 = 250), never n x (1 + r); round up; keep the "
                              "baseline sample as a separate reference value."),
            "source_inconsistencies": state.get("source_inconsistencies", []),
            "source_inconsistency_wording": SAFE_WORDING["source_inconsistency"]
            if state.get("source_inconsistencies") else ""}
