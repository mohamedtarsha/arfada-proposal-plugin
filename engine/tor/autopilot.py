"""Fast Proposal Mode autopilot (v0.6.5 — workflow only, engines unchanged).

Turns a parsed TOR + ARFADA Knowledge into a concrete, evidence-supported *Proposed
Setup* so Draft v1 can be generated with as few questions as possible:

  * auto-recommend every genuine proposal decision (assignment type, methodology,
    sample/FGD/KII counts, timeline, deliverables) as PROVISIONAL_RECOMMENDATION,
  * auto-rank the strongest provisional team and the strongest 3–5 past projects,
  * surface AT MOST 5 questions — only where an answer is truly necessary and cannot
    safely be recommended (budget ceiling, strategic methodology, sensitive
    previous-work sharing, ambiguous assignment type, a mandatory unknown fact).

This module only *computes* recommendations (deterministic, evidence-based). It never
invents facts and never approves anything — the caller persists provisional decisions
and the user approves or edits later. All existing safety engines are untouched.
"""
from __future__ import annotations

from typing import Any, Optional

from . import decision_ui

# Decision categories that should be auto-recommended rather than asked (§3).
_AUTO_CATEGORIES = {
    "assignment_type", "methodology", "sampling", "data_collection_methods",
    "evaluation_questions", "timeline", "deliverable", "team", "workplan",
}

# A question is justified only for these (§2). Priority order = list order.
_QUESTION_PRIORITY = [
    "assignment_type_ambiguous", "budget_ceiling", "strategic_methodology",
    "previous_work_sharing", "mandatory_unknown_fact",
]
_MAX_QUESTIONS = 5


def _mv(meta: dict, key: str) -> str:
    e = meta.get(key)
    return (e.get("value", "") if isinstance(e, dict) else "").strip()


def recommend_decisions(candidates: list[dict]) -> list[dict]:
    """Auto-recommend a value for every genuine human decision (PROVISIONAL)."""
    recs = []
    for c in candidates:
        if not c.get("is_human_decision"):
            continue
        desc = decision_ui.build_question_descriptor(c)
        if desc is None:
            continue
        value = desc.get("recommended_value")
        if value is None:
            # deferred / optional / open with no numeric/enum recommendation
            dtype = c.get("decision_type")
            if dtype == "DEFERRED_DECISION":
                value = "DEFER_TO_INCEPTION"
            elif dtype == "OPTIONAL_CHOICE":
                value = "INCLUDE"
            else:
                # pick the first concrete option value if any
                for o in desc.get("options", []):
                    if o.get("value") is not None:
                        value = o["value"]
                        break
        if value is None:
            continue
        recs.append({
            "decision_id": c["decision_id"],
            "requirement_id": c.get("requirement_id", ""),
            "category": c.get("category", ""),
            "value": value,
            "rationale": _rationale(c, value),
            "source_text": (c.get("source_text") or "")[:160],
        })
    return recs


def _rationale(c: dict, value: Any) -> str:
    ctype = c.get("constraint_type")
    if ctype == "AT_LEAST":
        return f"TOR requires at least {c.get('minimum')}; recommending the minimum {value}."
    if ctype == "RANGE":
        return f"TOR range {c.get('minimum')}–{c.get('maximum')}; recommending midpoint {value}."
    if ctype == "ENUM" or c.get("allowed_options"):
        return f"Recommending '{value}' from the TOR's allowed options."
    if c.get("decision_type") == "DEFERRED_DECISION":
        return "Recommending confirmation during inception (TOR permits deferral)."
    return f"Evidence-supported default for Draft v1: {value}."


def _ambiguous_assignment_type(tor: dict) -> tuple[bool, str, str]:
    at = tor.get("assignment_type", {})
    value = at.get("assignment_type") or at.get("type") or "OTHER"
    conf = (at.get("confidence") or "").upper()
    ambiguous = conf == "LOW" or value in ("", "OTHER", "UNKNOWN")
    return ambiguous, value, conf


def _budget_question_needed(requirements: list[dict], knowledge_has_rates: bool) -> bool:
    if knowledge_has_rates:
        return False
    for r in requirements:
        txt = (r.get("text") or "").lower()
        if any(k in txt for k in ("budget", "financial", "price", "cost", "fee")):
            return True
    return False


def _previous_work_requested(requirements: list[dict]) -> bool:
    for r in requirements:
        txt = (r.get("text") or "").lower()
        if ("previous" in txt or "sample" in txt or "example" in txt) and \
                any(k in txt for k in ("work", "report", "evaluation", "assignment", "deliverable")):
            return True
    return False


def build_questions(tor: dict, requirements: list[dict], *,
                    knowledge_has_rates: bool = False,
                    previous_work_cleared: bool = False) -> list[dict]:
    """Return AT MOST 5 genuinely-necessary questions (priority-ordered)."""
    q: list[dict] = []
    ambiguous, at_value, conf = _ambiguous_assignment_type(tor)
    if ambiguous:
        q.append({"key": "assignment_type_ambiguous", "decision_id": "assignment_type",
                  "question": "Which assignment type should this proposal target?",
                  "reason": f"Assignment-type inference is {conf or 'uncertain'} "
                            f"('{at_value}') — a wrong choice reshapes the whole proposal."})
    if _budget_question_needed(requirements, knowledge_has_rates):
        q.append({"key": "budget_ceiling",
                  "question": "What is the budget ceiling / pricing model for this bid?",
                  "reason": "A financial offer is required and no rates are available in "
                            "Knowledge; this cannot be safely guessed."})
    if _previous_work_requested(requirements) and not previous_work_cleared:
        q.append({"key": "previous_work_sharing",
                  "question": "May we share a specific previous-work report, and which one?",
                  "reason": "The TOR requests an example of previous work; sharing clearance "
                            "and the specific report are a human decision."})
    # cap + priority order
    q.sort(key=lambda x: _QUESTION_PRIORITY.index(x["key"])
           if x["key"] in _QUESTION_PRIORITY else 99)
    return q[:_MAX_QUESTIONS]


def rank_team(knowledge, requirements: list[dict], *, country: str = "",
              limit: int = 6) -> dict:
    """Rank CV candidates; pick the strongest provisional team (§8).

    Flags team_needs_question only when the top two are genuinely close, or no
    candidate is available for a mandatory role.
    """
    try:
        candidates = knowledge.search_staff(country=country or None, limit=limit)
    except Exception:
        candidates = []
    team = [{
        "staff_id": c.get("staff_id"),
        "name": c.get("name"),
        "roles": c.get("roles", []),
        "country": c.get("country", ""),
        "country_pool": c.get("country_pool", ""),
        "years_experience": c.get("years_experience"),
        "match_score": c.get("match_score", 0),
        # raw CV is read on demand for shortlisted people only (staff_pool.shortlist_details)
        "source_rel_path": c.get("source_rel_path", ""),
        "provisional": True,
    } for c in candidates]
    needs_question = False
    reason = ""
    if len(team) >= 2 and abs((team[0]["match_score"] or 0)
                              - (team[1]["match_score"] or 0)) <= 1:
        needs_question = True
        reason = "Top two candidates are closely ranked — confirm the lead."
    if not team:
        reason = "No CV candidates available in Knowledge (team is a gap, not a blocker)."
    pool = getattr(knowledge, "staff_pool_info", None) or {}
    return {"team": team[:5], "team_needs_question": needs_question, "reason": reason,
            "searchable_profiles": getattr(knowledge, "staff_pool_size",
                                           pool.get("count", 0)) if knowledge else 0,
            "staff_pool_source": pool.get("source", "")}


def rank_experience(knowledge, tor: dict, *, limit: int = 5) -> list[dict]:
    """Auto-select the strongest 3–5 past projects, excluding the current one (§9)."""
    meta = tor.get("metadata", {})
    at = tor.get("assignment_type", {})
    assignment_type = at.get("assignment_type") or at.get("type") or ""
    country = _mv(meta, "country")
    sector = _mv(meta, "sector")
    client = _mv(meta, "client")
    title = _mv(meta, "assignment") or _mv(meta, "title")
    try:
        return knowledge.relevant_projects(
            assignment_type=assignment_type or None, country=country or None,
            sector=sector or None, client=client or None,
            evaluation_type=assignment_type or None, thematic=title or None,
            exclude_current={"project_name": title, "assignment": title,
                             "country": country, "assignment_type": assignment_type},
            limit=limit)
    except Exception:
        return []


def build_proposed_setup(tor: dict, recommendations: list[dict], team: dict,
                         experience: list[dict]) -> dict:
    """Compact one-screen Proposed Setup summary (§3) — editable by the user."""
    at = tor.get("assignment_type", {})
    by_cat: dict[str, Any] = {}
    for r in recommendations:
        by_cat.setdefault(r["category"] or "other", []).append(
            {"value": r["value"], "rationale": r["rationale"]})
    return {
        "assignment_type": at.get("assignment_type") or at.get("type") or "OTHER",
        "assignment_confidence": at.get("confidence"),
        "decisions_by_category": by_cat,
        "team": team.get("team", []),
        "relevant_experience": [
            {"project": p.get("project_name") or p.get("project_id"),
             "country": p.get("country"), "type": p.get("assignment_type"),
             "score": p.get("match_score")}
            for p in experience],
        "note": "All items are PROVISIONAL recommendations for Draft v1 — edit any of "
                "them, then regenerate. Nothing here is a final client commitment.",
    }


def autopilot(tor: dict, requirements: list[dict], candidates: list[dict],
              knowledge=None, *, knowledge_has_rates: bool = False,
              previous_work_cleared: bool = False) -> dict:
    """Full Fast-Mode setup: recommendations + <=5 questions + team + experience."""
    meta = tor.get("metadata", {})
    country = _mv(meta, "country")
    recs = recommend_decisions(candidates)
    questions = build_questions(tor, requirements,
                                knowledge_has_rates=knowledge_has_rates,
                                previous_work_cleared=previous_work_cleared)
    team = rank_team(knowledge, requirements, country=country) if knowledge else \
        {"team": [], "team_needs_question": False, "reason": "No Knowledge connected."}
    experience = rank_experience(knowledge, tor) if knowledge else []
    setup = build_proposed_setup(tor, recs, team, experience)
    return {
        "recommendations": recs,
        "questions": questions,
        "question_count": len(questions),
        "team": team,
        "experience": experience,
        "proposed_setup": setup,
    }
