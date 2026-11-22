"""Final Quality Review — deterministic proposal acceptance (v0.6.0, PE7 lineage).

Consumes the existing run artifacts and produces a GREEN/YELLOW/RED verdict plus
structured findings. NO model call, NO network, NO new content. A finding is a
detected issue, never an auto-fix.

Overall status:
  RED    = one or more CRITICAL failures
  YELLOW = no CRITICAL, but material ERRORs or human-review items remain
  GREEN  = no CRITICAL, no material unresolved ERROR, mandatory coverage adequate

GREEN means "automated QA passed — ready for final HUMAN review", not "send blind".
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# severity ranks (lower = worse)
CRITICAL, ERROR, WARNING, INFO = "CRITICAL", "ERROR", "WARNING", "INFO"
_SEV_RANK = {CRITICAL: 0, ERROR: 1, WARNING: 2, INFO: 3}

QA_VERSION = 1


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    check: str
    severity: str
    category: str
    message: str
    evidence: str = ""
    section_id: str = ""
    requirement_id: str = ""
    recommended_action: str = ""
    blocks_client: bool = True

    @property
    def finding_id(self) -> str:
        key = "|".join([self.check, self.severity, self.section_id,
                        self.requirement_id, self.message[:80]])
        return "qa_" + hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:14]

    def as_dict(self) -> dict:
        return {
            "finding_id": self.finding_id, "check": self.check, "severity": self.severity,
            "category": self.category, "message": self.message, "evidence": self.evidence,
            "section_id": self.section_id, "requirement_id": self.requirement_id,
            "recommended_action": self.recommended_action, "blocks_client": self.blocks_client,
        }


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def _load(run_dir: Path, name: str) -> Optional[dict]:
    p = run_dir / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _section_text(candidate: dict) -> str:
    parts = []
    for b in candidate.get("blocks", []):
        t = b.get("type")
        if t in ("paragraph", "evidence_placeholder"):
            parts.append(b.get("text", ""))
        elif t in ("bullet_list", "numbered_list"):
            parts.extend(str(x) for x in b.get("items", []))
        elif t == "table":
            for row in b.get("rows", []):
                parts.extend(str(c) for c in row)
    return "\n".join(parts)


def _numbers_near(text: str, keyword_re: str) -> list[int]:
    """Numbers appearing within ~40 chars of a keyword (for metric-aware contradiction)."""
    out = []
    for m in re.finditer(keyword_re, text, re.I):
        window = text[max(0, m.start() - 40): m.end() + 40]
        for n in re.findall(r"\b(\d{1,5})\b", window):
            out.append(int(n))
    return out


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_final_qa(run_dir: str | Path, *, plugin_version: Optional[str] = None) -> dict:
    """Run all deterministic QA checks over a run directory. Returns the report dict."""
    run_dir = Path(run_dir)
    if plugin_version is None:
        from .version import plugin_version as _pv
        plugin_version = _pv()
    findings: list[Finding] = []

    tor = _load(run_dir, "tor_analysis.json") or {}
    reqs_doc = _load(run_dir, "requirements.json") or {}
    blueprint = _load(run_dir, "proposal_blueprint.json") or {}
    status_doc = _load(run_dir, "generation_status.json") or {}
    register = _load(run_dir, "decision_register.json")
    candidates_doc = _load(run_dir, "decision_candidates.json") or {}

    requirements = reqs_doc.get("requirements", [])
    run_id = tor.get("run_id")

    # load generated sections
    sections_dir = run_dir / "generated_sections"
    gen_sections: dict[str, dict] = {}
    if sections_dir.exists():
        for f in sections_dir.glob("*.json"):
            try:
                gen_sections[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    ctx = {
        "run_dir": run_dir, "tor": tor, "requirements": requirements,
        "blueprint": blueprint, "status": status_doc, "register": register,
        "candidates": candidates_doc, "gen_sections": gen_sections, "run_id": run_id,
    }

    # --- run checks ---
    findings += _check_artifact_consistency(ctx)
    findings += _check_requirement_coverage(ctx)
    findings += _check_ledger_substantive(ctx)
    findings += _check_ownership(ctx)
    findings += _check_fixed_constraints(ctx)
    findings += _check_decisions(ctx)
    findings += _check_personnel(ctx)
    findings += _check_arfada_facts(ctx)
    findings += _check_contradictions(ctx)
    findings += _check_assignment_type(ctx)
    findings += _check_section_completeness(ctx)
    findings += _check_framework(ctx)
    findings += _check_deliverables(ctx)
    findings += _check_workplan(ctx)
    findings += _check_team(ctx)
    findings += _check_submission(ctx)
    findings += _check_readability(ctx)
    findings += _check_duplication(ctx)
    findings += _check_client_leakage(ctx)
    findings += _check_historical_copy(ctx)
    findings += _check_claimed_annexes(ctx)
    findings += _check_budget_reconciliation(ctx)
    findings += _check_current_project_contamination(ctx)
    findings += _check_client_placeholders(ctx)
    findings += _check_sampling(ctx)
    # v0.6.11 claim gating (separate from numeric QA)
    findings += _check_claim_consistency(ctx)
    findings += _check_semantic_consistency(ctx)
    findings += _check_source_inconsistency(ctx)
    # v0.6.13 evidence-aware compliance + source semantics
    findings += _check_requirement_evidence(ctx)
    findings += _check_source_semantics(ctx)
    findings += _check_qualification_wording(ctx)

    # dedup
    seen, uniq = set(), []
    for f in findings:
        if f.finding_id in seen:
            continue
        seen.add(f.finding_id)
        uniq.append(f)
    uniq.sort(key=lambda f: (_SEV_RANK.get(f.severity, 9), f.check))

    counts = {}
    for f in uniq:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    overall = _rollup(uniq)
    summary = _summary(ctx, uniq, counts)

    fingerprint = _fingerprint(ctx, plugin_version)

    return {
        "qa_version": QA_VERSION,
        "run_id": run_id,
        "plugin_version": plugin_version,
        "overall_status": overall,
        "fingerprint": fingerprint,
        "summary": summary,
        "counts": counts,
        "critical_failures": [f.as_dict() for f in uniq if f.severity == CRITICAL],
        "errors": [f.as_dict() for f in uniq if f.severity == ERROR],
        "warnings": [f.as_dict() for f in uniq if f.severity == WARNING],
        "info": [f.as_dict() for f in uniq if f.severity == INFO],
        "findings": [f.as_dict() for f in uniq],
        # v0.6.13: evidence-aware coverage matrix + stored sample-size arithmetic
        "requirement_coverage": _coverage_rows(ctx),
        "sampling_provenance": ctx.get("sampling_provenance", {}),
    }


def _rollup(findings: list[Finding]) -> str:
    if any(f.severity == CRITICAL for f in findings):
        return "RED"
    if any(f.severity == ERROR for f in findings) or any(f.severity == WARNING for f in findings):
        return "YELLOW"
    return "GREEN"


def _summary(ctx, findings, counts) -> dict:
    reqs = [r for r in ctx["requirements"] if r.get("actor") != "CLIENT"]
    mandatory = [r for r in reqs if r.get("mandatory", True)]
    addressed = _addressed_requirement_ids(ctx)
    mand_addressed = sum(1 for r in mandatory if r["req_id"] in addressed)

    register = ctx["register"] or {}
    resolved = [d for d in register.get("decisions", [])
                if d.get("decision_status") == "RESOLVED"]
    dec_ok = sum(1 for d in resolved if _decision_respected(ctx, d))

    # v0.6.14: two separate summaries — CONTENT (does the text respond?) and EVIDENCE
    # (does ARFADA hold proof?) — plus QUALIFICATION_READINESS; an evidence gap is never
    # counted as a content gap
    from .response_coverage import coverage_summary
    cov = coverage_summary(_coverage_rows(ctx))
    return {
        "mandatory_requirements": len(mandatory),
        "mandatory_addressed": mand_addressed,
        "content_coverage": cov["content"],
        "evidence_coverage": cov["evidence"],
        "qualification_readiness": cov["qualification_readiness"],
        "qualifications": cov["qualifications"],
        "content_line": cov["content_line"],
        "evidence_line": cov["evidence_line"],
        "readiness_line": cov["readiness_line"],
        "critical_failures": counts.get(CRITICAL, 0),
        "errors": counts.get(ERROR, 0),
        "warnings": counts.get(WARNING, 0),
        "decisions_resolved": len(resolved),
        "decisions_respected": dec_ok,
        "sections_ready": sum(1 for s in ctx["status"].get("sections", {}).values()
                              if s.get("status") == "READY"),
        "sections_blocked": sum(1 for s in ctx["status"].get("sections", {}).values()
                                if s.get("status") == "BLOCKED_BY_DECISION"),
    }


# ---------------------------------------------------------------------------
# Fingerprint (spec §40)
# ---------------------------------------------------------------------------

def _fingerprint(ctx, plugin_version: str) -> str:
    parts = [plugin_version, str(ctx["run_id"])]
    tor = ctx["tor"]
    parts.append(str((tor.get("assignment_type") or {}).get("assignment_type")))
    reg = ctx["register"] or {}
    parts.append(str(reg.get("updated_at")))
    parts.append(str(len(reg.get("decisions", []))))
    # knowledge snapshot id
    man = _load(ctx["run_dir"], "knowledge_snapshot/knowledge_manifest.json")
    parts.append(str((man or {}).get("snapshot_id")))
    # section content hashes
    for sid in sorted(ctx["gen_sections"]):
        body = json.dumps(ctx["gen_sections"][sid], sort_keys=True, ensure_ascii=False)
        parts.append(sid + ":" + hashlib.sha1(body.encode()).hexdigest()[:10])
    return "qafp_" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Coverage helpers
# ---------------------------------------------------------------------------

def _responses(ctx) -> dict:
    """v0.6.14: RESPONSE_STATUS per requirement, computed from the generated text and the
    requirement → section mapping (the ledger's status label is ignored)."""
    if "_responses" not in ctx:
        from .response_coverage import compute_responses
        meta = ctx["tor"].get("metadata", {}) or {}
        places = list(((meta.get("subnational_location") or {}).get("values") or [])) \
            if isinstance(meta.get("subnational_location"), dict) else []
        ctx["_responses"] = compute_responses(
            ctx["requirements"], ctx["gen_sections"],
            section_status=ctx["status"].get("sections", {}), blueprint=ctx["blueprint"],
            places=places)
    return ctx["_responses"]


def _addressed_requirement_ids(ctx) -> set:
    """Requirement ids the proposal TEXT addresses (computed — never self-declared)."""
    from .response_coverage import ADDRESSED
    return {rid for rid, r in _responses(ctx).items() if r["response_status"] == ADDRESSED}


def _ledger_addressed_ids(ctx) -> set:
    """Requirement ids whose ledger status is ADDRESSED in a READY section (legacy:
    used only to skip package-item checks, which the claim state governs)."""
    out = set()
    status = ctx["status"].get("sections", {})
    for sid, cand in ctx["gen_sections"].items():
        if status.get(sid, {}).get("status") != "READY":
            continue
        for e in cand.get("requirement_response_ledger", []):
            if e.get("status") == "ADDRESSED":
                out.add(e.get("requirement_id"))
    return out


# ---------------------------------------------------------------------------
# CHECK: artifact consistency
# ---------------------------------------------------------------------------

def _check_artifact_consistency(ctx) -> list[Finding]:
    out = []
    run_id = ctx["run_id"]
    for name, doc in (("requirements.json", {"run_id": (_load(ctx['run_dir'],'requirements.json') or {}).get('run_id')}),
                      ("proposal_blueprint.json", ctx["blueprint"]),
                      ("generation_status.json", ctx["status"])):
        rid = doc.get("run_id")
        if rid and run_id and rid != run_id:
            out.append(Finding("ARTIFACT_CONSISTENCY", CRITICAL, "cross_run",
                               f"{name} run_id '{rid}' does not match TOR run_id '{run_id}'",
                               recommended_action="Re-run analysis/generation on one TOR."))
    reg = ctx["register"]
    if reg and reg.get("run_id") and run_id and reg["run_id"] != run_id:
        out.append(Finding("ARTIFACT_CONSISTENCY", CRITICAL, "cross_run",
                           "decision_register run_id mismatch (cross-TOR contamination)"))
    return out


# ---------------------------------------------------------------------------
# CHECK: requirement coverage
# ---------------------------------------------------------------------------

def _check_requirement_coverage(ctx) -> list[Finding]:
    out = []
    status = ctx["status"].get("sections", {})
    # map requirement -> owning section via blueprint
    owner = {}
    for s in ctx["blueprint"].get("sections", []):
        for rid in s.get("requirement_ids", []):
            owner[rid] = s["section_id"]

    addressed = _addressed_requirement_ids(ctx)
    for r in ctx["requirements"]:
        if r.get("actor") == "CLIENT":
            continue
        # Submission/compliance items are owned by _check_submission, which grades
        # them by obligation (mandatory vs scoring/competitive vs optional) so a
        # competitive item never forces RED here.
        if r.get("category") == "submission":
            continue
        rid = r["req_id"]
        mandatory = r.get("mandatory", True)
        sec = owner.get(rid, "")
        sec_status = status.get(sec, {}).get("status")
        if rid in addressed:
            continue
        if sec_status == "BLOCKED_BY_DECISION":
            if mandatory:
                out.append(Finding("REQUIREMENT_COVERAGE", ERROR, "coverage",
                                   "Mandatory requirement blocked by an unresolved decision",
                                   evidence=r.get("text", "")[:120], section_id=sec,
                                   requirement_id=rid,
                                   recommended_action="Resolve the dependent decision, regenerate."))
            continue
        # v0.6.14: the text responds only in part — a content weakness to review, not a
        # missing requirement (an evidence gap never reaches this check)
        resp = _responses(ctx).get(rid) or {}
        if resp.get("response_status") == "PARTIALLY_ADDRESSED":
            out.append(Finding("REQUIREMENT_COVERAGE", WARNING if mandatory else INFO,
                               "partial_response",
                               ("Mandatory requirement only partially answered in the text: "
                                if mandatory else "Optional requirement partially answered: ")
                               + resp.get("response_basis", ""),
                               evidence=r.get("text", "")[:120], section_id=sec,
                               requirement_id=rid, blocks_client=False,
                               recommended_action="Complete the response in the owning section."))
            continue
        # not addressed, not blocked
        sev = CRITICAL if mandatory else INFO
        out.append(Finding("REQUIREMENT_COVERAGE", sev, "coverage",
                           ("Mandatory requirement MISSING from generated proposal"
                            if mandatory else "Optional requirement not addressed"),
                           evidence=r.get("text", "")[:120], section_id=sec,
                           requirement_id=rid,
                           recommended_action="Generate/repair the owning section to cover it."))
    return out


# ---------------------------------------------------------------------------
# CHECK: ledger substantive (detect false coverage)
# ---------------------------------------------------------------------------

_TRIVIAL = re.compile(
    r"^\s*(?:[\w\s]+ will be (?:conducted|undertaken|carried out|done|provided|ensured)"
    r"|we will (?:conduct|undertake|provide|ensure)[\w\s]{0,20})\.?\s*$", re.I)


def _check_ledger_substantive(ctx) -> list[Finding]:
    out = []
    status = ctx["status"].get("sections", {})
    for sid, cand in ctx["gen_sections"].items():
        if status.get(sid, {}).get("status") != "READY":
            continue
        block_text = {b.get("block_id"): _block_text(b) for b in cand.get("blocks", [])}
        for e in cand.get("requirement_response_ledger", []):
            if e.get("status") != "ADDRESSED":
                continue
            bids = e.get("block_ids", [])
            # block existence
            missing = [b for b in bids if b not in block_text]
            if missing:
                out.append(Finding("LEDGER_VERIFICATION", ERROR, "false_coverage",
                                   f"Ledger claims ADDRESSED but references missing block(s) {missing}",
                                   section_id=sid, requirement_id=e.get("requirement_id"),
                                   recommended_action="Fix block_ids or regenerate the section."))
                continue
            joined = " ".join(block_text.get(b, "") for b in bids).strip()
            if len(joined.split()) < 6:
                out.append(Finding("LEDGER_VERIFICATION", WARNING, "false_coverage",
                                   "Ledger claims ADDRESSED but the referenced content is very thin",
                                   evidence=joined[:80], section_id=sid,
                                   requirement_id=e.get("requirement_id"),
                                   recommended_action="Expand the response to substantively address the requirement.",
                                   blocks_client=False))
            elif _TRIVIAL.match(joined):
                out.append(Finding("LEDGER_VERIFICATION", WARNING, "false_coverage",
                                   "Response restates the requirement without a substantive approach",
                                   evidence=joined[:80], section_id=sid,
                                   requirement_id=e.get("requirement_id"),
                                   recommended_action="Describe HOW, not just THAT.",
                                   blocks_client=False))
    return out


def _block_text(b: dict) -> str:
    t = b.get("type")
    if t in ("paragraph", "evidence_placeholder"):
        return b.get("text", "")
    if t in ("bullet_list", "numbered_list"):
        return " ".join(str(x) for x in b.get("items", []))
    if t == "table":
        return " ".join(str(c) for row in b.get("rows", []) for c in row)
    return ""


# ---------------------------------------------------------------------------
# CHECK: ownership
# ---------------------------------------------------------------------------

def _check_ownership(ctx) -> list[Finding]:
    out = []
    owner_count: dict[str, int] = {}
    for s in ctx["blueprint"].get("sections", []):
        for rid in s.get("requirement_ids", []):
            owner_count[rid] = owner_count.get(rid, 0) + 1
    # submission/compliance items are package items (handled by _check_submission),
    # not prose sections — they are not "orphans" when unowned.
    submission_ids = {r["req_id"] for r in ctx["requirements"]
                      if r.get("category") == "submission"}
    bidder = {r["req_id"] for r in ctx["requirements"]
              if r.get("actor") != "CLIENT" and r["req_id"] not in submission_ids}
    for rid in bidder:
        c = owner_count.get(rid, 0)
        if c == 0:
            out.append(Finding("OWNERSHIP", CRITICAL, "orphan",
                               "Bidder requirement has no owning section (orphan)",
                               requirement_id=rid,
                               recommended_action="Rebuild the blueprint."))
        elif c > 1:
            out.append(Finding("OWNERSHIP", ERROR, "duplicate_ownership",
                               f"Requirement owned by {c} sections (duplicate)",
                               requirement_id=rid))
    # client requirement treated as bidder slot
    client_ids = {r["req_id"] for r in ctx["requirements"] if r.get("actor") == "CLIENT"}
    slot_reqs = {s["requirement_id"] for s in ctx["blueprint"].get("slots", [])}
    for rid in client_ids & slot_reqs:
        out.append(Finding("OWNERSHIP", ERROR, "client_as_bidder",
                           "Client-responsibility requirement treated as a bidder obligation",
                           requirement_id=rid))
    return out


# ---------------------------------------------------------------------------
# CHECK: fixed TOR constraints
# ---------------------------------------------------------------------------

def _check_fixed_constraints(ctx) -> list[Finding]:
    out = []
    all_text = _all_generated_text(ctx)
    for c in ctx["candidates"].get("candidates", []):
        ctype = c.get("constraint_type")
        mn, mx = c.get("minimum"), c.get("maximum")
        if ctype == "AT_MOST" and mx is not None:
            # a number clearly above the max near the same unit → violation
            for n in _numbers_near(all_text, re.escape(str(c.get("category", "")))):
                pass  # category-based is weak; rely on page/number scan below
    # page limit
    page_limit = _page_limit(ctx)
    if page_limit:
        # we cannot measure rendered pages deterministically; warn only
        out.append(Finding("FIXED_CONSTRAINT", INFO, "page_limit",
                           f"TOR page limit is {page_limit}; verify the client DOCX length before submission",
                           recommended_action="Check rendered page count manually.",
                           blocks_client=False))
    return out


def _page_limit(ctx) -> Optional[int]:
    meta = ctx["tor"].get("metadata", {})
    pl = meta.get("page_limits")
    if isinstance(pl, dict):
        m = re.search(r"\b(\d{1,3})\b", pl.get("value", ""))
        return int(m.group(1)) if m else None
    return None


# ---------------------------------------------------------------------------
# CHECK: decisions
# ---------------------------------------------------------------------------

def _decision_respected(ctx, d: dict) -> bool:
    val = d.get("selected_value")
    if val is None:
        return True
    text = _all_generated_text(ctx)
    if isinstance(val, (int, float)):
        iv = int(val) if float(val).is_integer() else val
        return str(iv) in text
    return True  # non-numeric: presence is not deterministically checkable


def _check_decisions(ctx) -> list[Finding]:
    out = []
    register = ctx["register"]
    if not register:
        return out
    text = _all_generated_text(ctx)
    for d in register.get("decisions", []):
        st = d.get("decision_status")
        val = d.get("selected_value")
        if st == "RESOLVED" and isinstance(val, (int, float)):
            iv = int(val) if float(val).is_integer() else val
            mn = d.get("minimum")
            if str(iv) not in text:
                # the approved value is not present — only an issue if the metric is
                # discussed; conservative ERROR
                out.append(Finding("DECISION_COMPLIANCE", ERROR, "decision_ignored",
                                   f"Approved decision value {iv} not found in the proposal",
                                   requirement_id=d.get("requirement_id"),
                                   recommended_action="Use the approved value exactly in the owning section.",
                                   blocks_client=False))
            # a conflicting below-minimum number near the same requirement
            if mn is not None:
                # only CURRENT counts of this decision's metric (not past-project
                # statistics or breakdown rows) can conflict with its minimum
                from .numeric_claims import decision_targets
                metric = next((m for m, v in decision_targets(
                    {"decisions": [{**d, "decision_status": "RESOLVED"}]}).items()), None)
                cur = _current_claims(ctx).get(metric, []) if metric else []
                below = [c.value for c in cur if c.value < mn and c.value != 0]
                if below and str(iv) in text:
                    out.append(Finding("DECISION_COMPLIANCE", CRITICAL, "decision_conflict",
                                       f"A value below the TOR minimum {mn} appears alongside the approved {iv}",
                                       evidence=f"below-min values: {sorted(set(below))}",
                                       requirement_id=d.get("requirement_id")))
        if st in ("OPEN", "UNRESOLVED", "SKIPPED") and isinstance(val, (int, float)):
            out.append(Finding("DECISION_COMPLIANCE", CRITICAL, "fabricated_decision",
                               "An unresolved decision has a concrete value (fabricated resolution)",
                               requirement_id=d.get("requirement_id")))
    return out


# ---------------------------------------------------------------------------
# CHECK: personnel
# ---------------------------------------------------------------------------

def _check_personnel(ctx) -> list[Finding]:
    out = []
    # named staff must correspond to an approved staff decision
    register = ctx["register"] or {}
    approved_staff = {str(d.get("selected_value")) for d in register.get("decisions", [])
                      if d.get("category") == "staff" and d.get("decision_status") == "RESOLVED"}
    team = ctx["gen_sections"].get("TEAM")
    if not team:
        return out
    text = _section_text(team)
    # detect titled personal names (Dr/Mr/Ms X) that are not TO_BE_NOMINATED
    for m in re.finditer(r"\b(?:Dr|Mr|Ms|Mrs|Prof|Eng)\.?\s+([A-Z][a-z]+)", text):
        name = m.group(0)
        if name not in approved_staff and "to be nominated" not in text.lower():
            out.append(Finding("PERSONNEL", ERROR, "unapproved_staff",
                               f"Named individual '{name}' is not an approved staff selection",
                               section_id="TEAM", evidence=name,
                               recommended_action="Use 'To be nominated' or approve the person via Decision Review."))
    return out


# ---------------------------------------------------------------------------
# CHECK: ARFADA facts
# ---------------------------------------------------------------------------

_ARFADA_NUM = re.compile(
    r"ARFADA[^.]{0,60}?\b(\d{2,6})\b|\b(\d{2,6})\b[^.]{0,30}?(?:surveys?|kiis?|fgds?|"
    r"projects?|evaluations?|countries|years)", re.I)


def _check_arfada_facts(ctx) -> list[Finding]:
    out = []
    verified = _verified_fact_numbers(ctx)
    for sid, cand in ctx["gen_sections"].items():
        text = _section_text(cand)
        has_placeholder = any(b.get("type") == "evidence_placeholder" for b in cand.get("blocks", []))
        if "NEEDS_ARFADA_EVIDENCE" in text or has_placeholder:
            continue
        # v0.6.12 typed tokens: "73,906" is one number; identifiers ("CFGB 3350"),
        # durations ("30 days"), percentages, years and this proposal's methodology
        # counts are not ARFADA organisational metrics and are never checked here
        from .numeric_tokens import tokenize
        for sent in re.findall(r"(?:[^.;!?\n]|\.(?=\d))+[.;!?]?", text):
            if not re.search(r"\bARFADA\b", sent):
                continue
            for tok in tokenize(sent):
                if tok.kind != "PORTFOLIO_METRIC":
                    continue
                if str(tok.int_value) not in verified:
                    out.append(Finding("ARFADA_FACT", ERROR, "unsupported_fact",
                                       f"Unsupported ARFADA number '{tok.raw}' not in the "
                                       "knowledge snapshot",
                                       evidence=sent.strip()[:120], section_id=sid,
                                       recommended_action="Cite a verified fact_id or use NEEDS_ARFADA_EVIDENCE."))
    return out


def _verified_fact_numbers(ctx) -> set:
    nums = set()
    # from knowledge snapshot metrics
    man = _load(ctx["run_dir"], "knowledge_snapshot/projects.json")
    if man:
        for k, v in (man.get("metrics", {}) or {}).items():
            val = v.get("value") if isinstance(v, dict) else v
            if isinstance(val, (int, float)):
                nums.add(str(int(val)))
    return nums


# ---------------------------------------------------------------------------
# CHECK: contradictions
# ---------------------------------------------------------------------------

def _current_claims(ctx) -> dict:
    """Current-methodology counts per metric (historical/reference numbers excluded)."""
    from .numeric_claims import current_claims
    exclude = {int(n) for n in _verified_fact_numbers(ctx)}   # ARFADA portfolio metrics
    return current_claims(ctx["gen_sections"], exclude_values=exclude)


def _check_contradictions(ctx) -> list[Finding]:
    """Section- and entity-aware numeric consistency.

    Only the proposal's CURRENT methodology counts are compared — past-project
    statistics, ARFADA portfolio totals, reference values (minimum/baseline/reserve)
    and breakdown rows are excluded; breakdown tables are summed and must equal the
    stated total. When the run has an approved or provisional decision for a
    metric, every current count must equal it.
    """
    from .numeric_claims import decision_targets
    out = []
    claims = _current_claims(ctx)
    targets = decision_targets(ctx.get("register"))
    for metric, items in claims.items():
        if not items:
            continue
        vals = sorted({c.value for c in items})
        target = targets.get(metric)
        if target is not None:
            wrong = sorted({c.value for c in items if c.value != target})
            if wrong:
                where = sorted({c.section_id for c in items if c.value != target})
                out.append(Finding("CONTRADICTION", ERROR, "numeric_contradiction",
                                   f"{metric} count {wrong} differs from the current-run "
                                   f"decision ({target})",
                                   evidence="; ".join(c.snippet for c in items
                                                      if c.value != target)[:200],
                                   section_id=where[0] if where else "",
                                   recommended_action=f"Use {target} for the {metric} total "
                                                      "(or edit the decision)."))
        elif len(vals) > 1:
            out.append(Finding("CONTRADICTION", ERROR, "numeric_contradiction",
                               f"Conflicting current {metric} counts across sections: {vals}",
                               evidence="; ".join(f"{c.section_id}: {c.value}"
                                                  for c in items)[:200],
                               recommended_action="Align all sections to the approved count."))
    # v0.6.12 sampling provenance: minimum → allowance → adjusted → proposed (rounded up);
    # the baseline sample is recorded separately and never treated as a contradiction
    from .numeric_claims import sampling_provenance, is_historical_section
    current_text = "\n".join(_section_text(c) for sid, c in ctx["gen_sections"].items()
                             if not is_historical_section(sid))
    prov = sampling_provenance(current_text)
    ctx["sampling_provenance"] = prov
    if prov["found"] and not prov["consistent"]:
        out.append(Finding("SAMPLING_PROVENANCE", WARNING, "sampling_arithmetic",
                           "Sample-size derivation does not reconcile: " + "; ".join(prov["issues"]),
                           blocks_client=False,
                           recommended_action="State minimum, allowance, adjusted value and the "
                                              "rounded-up proposed sample consistently."))
    # entity contradiction: client/country
    meta = ctx["tor"].get("metadata", {})
    for key, label in (("client", "client"), ("country", "country")):
        v = (meta.get(key) or {}).get("value", "") if isinstance(meta.get(key), dict) else ""
        # (entity drift detection is conservative; skipped unless metadata present)
    return out


# ---------------------------------------------------------------------------
# CHECK: assignment type terminology
# ---------------------------------------------------------------------------

def _check_assignment_type(ctx) -> list[Finding]:
    out = []
    at = (ctx["tor"].get("assignment_type") or {}).get("assignment_type", "")
    bp_type = ctx["blueprint"].get("assignment_type", "")
    if at and bp_type and at != bp_type:
        # allowed if a classification decision resolved it
        out.append(Finding("ASSIGNMENT_TYPE", WARNING, "type_mismatch",
                           f"Inferred type '{at}' differs from blueprint type '{bp_type}'",
                           blocks_client=False))
    # terminology: a non-evaluation assignment should not be called an evaluation throughout
    if bp_type and bp_type not in ("EVALUATION", "MIDLINE", "ENDLINE"):
        eval_hits = 0
        for cand in ctx["gen_sections"].values():
            eval_hits += len(re.findall(r"\bevaluation\b", _section_text(cand), re.I))
        if eval_hits >= 5:
            out.append(Finding("ASSIGNMENT_TYPE", WARNING, "wrong_terminology",
                               f"Assignment is {bp_type} but 'evaluation' appears {eval_hits} times",
                               recommended_action="Use assignment-type-appropriate terminology.",
                               blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# CHECK: section completeness
# ---------------------------------------------------------------------------

def _check_section_completeness(ctx) -> list[Finding]:
    out = []
    status = ctx["status"].get("sections", {})
    for s in ctx["blueprint"].get("sections", []):
        sid = s["section_id"]
        st = status.get(sid, {}).get("status")
        required = s.get("required", False)
        if st == "FAILED":
            out.append(Finding("SECTION_COMPLETENESS", CRITICAL if required else ERROR,
                               "section_failed", f"Section {sid} failed generation",
                               section_id=sid))
        elif st == "BLOCKED_BY_DECISION" and required and s.get("mandatory_requirement_ids"):
            out.append(Finding("SECTION_COMPLETENESS", ERROR, "section_blocked",
                               f"Required section {sid} is blocked by an unresolved decision",
                               section_id=sid, blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# CHECK: framework
# ---------------------------------------------------------------------------

def _check_framework(ctx) -> list[Finding]:
    out = []
    fw = ctx["blueprint"].get("framework_section")
    if not fw:
        return out
    status = ctx["status"].get("sections", {})
    # framework only required if it has owned requirements / eval questions
    sec = next((s for s in ctx["blueprint"]["sections"] if s["section_id"] == fw), None)
    if not sec or not sec.get("requirement_ids"):
        return out
    st = status.get(fw, {}).get("status")
    if st != "READY":
        return out  # completeness check handles non-ready
    cand = ctx["gen_sections"].get(fw, {})
    tables = [b for b in cand.get("blocks", []) if b.get("type") == "table"]
    if not tables:
        out.append(Finding("FRAMEWORK", CRITICAL, "missing_matrix",
                           f"Framework section {fw} has no matrix table",
                           section_id=fw,
                           recommended_action="Generate the framework as a table with the required columns."))
    else:
        if not any(t.get("rows") for t in tables):
            out.append(Finding("FRAMEWORK", ERROR, "empty_matrix",
                               f"Framework table in {fw} has no rows", section_id=fw))
    return out


# ---------------------------------------------------------------------------
# CHECK: deliverables
# ---------------------------------------------------------------------------

def _check_deliverables(ctx) -> list[Finding]:
    out = []
    deliv_reqs = [r for r in ctx["requirements"]
                  if r.get("category") == "deliverable" and r.get("actor") != "CLIENT"
                  and r.get("mandatory", True)]
    if not deliv_reqs:
        return out
    cand = ctx["gen_sections"].get("DELIVERABLES")
    status = ctx["status"].get("sections", {})
    if status.get("DELIVERABLES", {}).get("status") != "READY":
        if deliv_reqs:
            out.append(Finding("DELIVERABLES", CRITICAL, "missing_deliverables_section",
                               "TOR has deliverables but the DELIVERABLES section is not ready",
                               section_id="DELIVERABLES"))
        return out
    # v0.6.16: the computed RESPONSE_STATUS (text + mapping), not the ledger's label
    addressed = _addressed_requirement_ids(ctx)
    for r in deliv_reqs:
        if r["req_id"] not in addressed:
            out.append(Finding("DELIVERABLES", CRITICAL, "missing_deliverable",
                               "Mandatory TOR deliverable not addressed",
                               evidence=r.get("text", "")[:100], section_id="DELIVERABLES",
                               requirement_id=r["req_id"]))
    return out


# ---------------------------------------------------------------------------
# CHECK: workplan
# ---------------------------------------------------------------------------

def _check_workplan(ctx) -> list[Finding]:
    out = []
    cand = ctx["gen_sections"].get("WORKPLAN")
    if not cand:
        return out
    text = _section_text(cand)
    # duration contradictions (weeks)
    weeks = sorted(set(int(m.group(1)) for m in re.finditer(r"\b(\d{1,2})\s*weeks?\b", text, re.I)))
    if len(weeks) > 3:
        out.append(Finding("WORKPLAN", WARNING, "timeline_spread",
                           f"Many distinct week durations in workplan: {weeks}",
                           section_id="WORKPLAN", blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# CHECK: team
# ---------------------------------------------------------------------------

def _check_team(ctx) -> list[Finding]:
    out = []
    team_reqs = [r for r in ctx["requirements"]
                 if r.get("category") == "team" and r.get("actor") != "CLIENT"]
    if not team_reqs:
        return out
    status = ctx["status"].get("sections", {})
    if status.get("TEAM", {}).get("status") not in ("READY", "BLOCKED_BY_DECISION"):
        out.append(Finding("TEAM", ERROR, "team_missing",
                           "TOR defines team requirements but TEAM section is not ready",
                           section_id="TEAM", blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# CHECK: submission / compliance
# ---------------------------------------------------------------------------

def _check_submission(ctx) -> list[Finding]:
    """Report EACH missing submission item by its real identity + obligation.

    Mandatory compliance failures are CRITICAL (RED). Scoring/competitive gaps are
    WARNING (YELLOW at most — a competitive improvement never forces RED unless the
    TOR makes it mandatory). Optional gaps are INFO.
    """
    from .submission import classify_submission_requirement, MANDATORY, SCORING
    out = []
    sub_reqs = [r for r in ctx["requirements"]
                if r.get("category") == "submission" and r.get("actor") != "CLIENT"]
    if not sub_reqs:
        return out
    from .submission import is_status_item, requires_physical_annex
    addressed = _ledger_addressed_ids(ctx)
    proposal_text = _all_generated_text(ctx).lower()
    for r in sub_reqs:
        if r["req_id"] in addressed:
            continue
        entry = classify_submission_requirement(r)
        item = entry["item_label"]
        obligation = entry["obligation"]
        # v0.6.12: deadline / channel lines are status items (claim-state blockers),
        # and a content item (e.g. "Risk Mitigation Plan") is satisfied when the
        # technical proposal covers it — only physical annexes stay package items
        if is_status_item(entry["text"]):
            continue
        # v0.6.16: a physical annex the package verifiably holds (claim state checks the
        # actual files: CV manifest, cleared + annexed report, budget, registration file)
        claim_key = {"cv_annex": "team_cv_package", "previous_work": "previous_work_sample",
                     "detailed_budget": "financial_proposal",
                     "registration": "registration_evidence"}.get(entry["item_key"])
        if claim_key and ((_claim_state(ctx).get("claims") or {}).get(claim_key) or {}).get(
                "status") == "VERIFIED":
            continue
        if not requires_physical_annex(entry):
            # a content item is answered by the technical proposal itself: satisfied if
            # the proposal covers it by name ("Work plan / timeline" → either variant)
            variants = [re.sub(r"[…\.]+$", "", v).strip().lower()
                        for v in re.split(r"\s*/\s*", item)]
            if any(len(v.split()) >= 2 and v in proposal_text for v in variants) or \
                    any(len(v.split()) == 1 and len(v) > 4 and re.search(rf"\b{re.escape(v)}\b",
                                                                        proposal_text)
                        for v in variants):
                continue
            if obligation == MANDATORY:
                # not a missing package file: a draft-coverage gap (never Annex: other)
                out.append(Finding("SUBMISSION", WARNING, "content_item_not_addressed",
                                   f"TOR content item not yet covered in the proposal: {item}",
                                   evidence=entry["text"][:140], section_id="SUBMISSION",
                                   requirement_id=r["req_id"], blocks_client=False,
                                   recommended_action=f"Cover '{item}' in the technical proposal."))
                continue
        if obligation == MANDATORY:
            out.append(Finding("SUBMISSION", CRITICAL, "mandatory_submission_missing",
                               f"Mandatory submission item missing: {item}",
                               evidence=entry["text"][:140], section_id="SUBMISSION",
                               requirement_id=r["req_id"], blocks_client=True,
                               recommended_action=f"Provide/address: {item}."))
        elif obligation == SCORING:
            out.append(Finding("SUBMISSION", WARNING, "scoring_submission_missing",
                               f"Scoring/competitive item not yet addressed: {item}",
                               evidence=entry["text"][:140], section_id="SUBMISSION",
                               requirement_id=r["req_id"], blocks_client=False,
                               recommended_action=f"Strengthen competitiveness: {item} "
                                                  "(not mandatory — will not block export)."))
        else:
            out.append(Finding("SUBMISSION", INFO, "optional_submission_missing",
                               f"Optional item not included: {item}",
                               section_id="SUBMISSION", requirement_id=r["req_id"],
                               blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# CHECK: readability
# ---------------------------------------------------------------------------

def _check_readability(ctx) -> list[Finding]:
    out = []
    for sid, cand in ctx["gen_sections"].items():
        for b in cand.get("blocks", []):
            if b.get("type") == "paragraph":
                wc = len(b.get("text", "").split())
                if wc > 180:
                    out.append(Finding("READABILITY", WARNING, "long_paragraph",
                                       f"Paragraph of {wc} words (>180) in {sid}",
                                       section_id=sid, blocks_client=False,
                                       recommended_action="Split into shorter paragraphs or a list."))
    return out


# ---------------------------------------------------------------------------
# CHECK: duplication
# ---------------------------------------------------------------------------

def _check_duplication(ctx) -> list[Finding]:
    out = []
    seen: dict[str, str] = {}
    for sid, cand in ctx["gen_sections"].items():
        for b in cand.get("blocks", []):
            if b.get("type") == "paragraph":
                norm = re.sub(r"\s+", " ", b.get("text", "").strip().lower())
                if len(norm) < 50:
                    continue
                key = norm[:120]
                if key in seen and seen[key] != sid:
                    out.append(Finding("DUPLICATION", WARNING, "duplicate_paragraph",
                                       f"Near-identical paragraph repeated in {seen[key]} and {sid}",
                                       section_id=sid, blocks_client=False))
                else:
                    seen[key] = sid
    return out


# ---------------------------------------------------------------------------
# CHECK: client leakage (internal markers)
# ---------------------------------------------------------------------------

_INTERNAL_MARKERS = ("NEEDS_ARFADA_EVIDENCE", "BLOCKED_BY_DECISION", "req_", "slot_",
                     "fact_id", "snap_", "qa_", "Master Tracker", "master_tracker",
                     "knowledge snapshot", "knowledge_snapshot", "STATIC_FALLBACK",
                     "LOCAL_FOLDER", "GOOGLE_API", "Knowledge folder", ".arfada-proposal")


def _check_client_leakage(ctx) -> list[Finding]:
    out = []
    client_docx = ctx["run_dir"] / "proposal_client_draft.docx"
    if not client_docx.exists():
        return out
    try:
        import sys
        deps = Path(__file__).resolve().parent.parent.parent / ".mcp_deps"
        if deps.exists() and str(deps) not in sys.path:
            sys.path.insert(0, str(deps))
        from docx import Document
        doc = Document(str(client_docx))
        text = "\n".join(p.text for p in doc.paragraphs)
        for t in doc.tables:
            for row in t.rows:
                for c in row.cells:
                    text += "\n" + c.text
    except Exception:
        return out
    run_dir_str = str(ctx["run_dir"])
    if run_dir_str in text:
        out.append(Finding("CLIENT_LEAKAGE", CRITICAL, "path_leak",
                           "Client DOCX exposes a local filesystem path"))
    for marker in _INTERNAL_MARKERS:
        if marker in text:
            out.append(Finding("CLIENT_LEAKAGE", CRITICAL, "internal_marker",
                               f"Client DOCX exposes internal marker '{marker}'"))
    return out


# ---------------------------------------------------------------------------
# shared text
# ---------------------------------------------------------------------------

def _all_generated_text(ctx) -> str:
    return "\n".join(_section_text(c) for c in ctx["gen_sections"].values())


# ---------------------------------------------------------------------------
# CHECK: historical exemplar copy / leakage (v0.6.1)
# ---------------------------------------------------------------------------

def _check_historical_copy(ctx) -> list[Finding]:
    """Flag verbatim copying of, or entity leakage from, the winning-proposal library.

    Uses the packet's historical_exemplars if present (what was actually shown to
    generation). Silent no-op when the exemplar library isn't configured.
    """
    out = []
    try:
        from .exemplars.anticopy import similarity_report, leaked_historical_entities
    except Exception:
        return out
    packets_dir = ctx["run_dir"] / "generation_packets"
    if not packets_dir.exists():
        return out
    for sid, cand in ctx["gen_sections"].items():
        pk_path = packets_dir / f"{sid}.json"
        if not pk_path.exists():
            continue
        try:
            packet = json.loads(pk_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        exemplars = packet.get("historical_exemplars", [])
        if not exemplars:
            continue
        text = _section_text(cand)
        excerpts = [e.get("style_excerpt", "") for e in exemplars]
        sim = similarity_report(text, excerpts)
        if sim["flagged"]:
            out.append(Finding("HISTORICAL_COPY", ERROR, "verbatim_similarity",
                               f"Section too similar to a historical exemplar ({sim['detail']})",
                               section_id=sid,
                               recommended_action="Rewrite in ARFADA style without copying."))
        leaks = leaked_historical_entities(text, exemplars)
        if leaks:
            out.append(Finding("HISTORICAL_COPY", CRITICAL, "entity_leak",
                               f"Historical project/client token(s) {leaks} leaked into the proposal",
                               section_id=sid,
                               recommended_action="Remove old client/project references."))
    return out


# ---------------------------------------------------------------------------
# CHECK: claimed annexes whose files do not exist (§9)
# ---------------------------------------------------------------------------

_ANNEX_CLAIM = {
    "cvs": re.compile(r"\b(cv[s]?|curriculum vit\w+|r[eé]sum[eé]s?)\b[^.\n]{0,60}"
                      r"\b(annex\w*|attach\w*|append\w*|enclos\w*|provided)\b", re.I),
    "previous_work": re.compile(r"\b(example|sample)\b[^.\n]{0,40}\b(previous|past)\b"
                                r"[^.\n]{0,40}\b(annex\w*|attach\w*|append\w*|enclos\w*)\b", re.I),
    "budget": re.compile(r"\b(detailed budget|financial (?:offer|proposal)|budget)\b"
                         r"[^.\n]{0,50}\b(annex\w*|attach\w*|append\w*|enclos\w*|separate)\b", re.I),
}


def _check_claimed_annexes(ctx) -> list[Finding]:
    """If the proposal text claims an annex (CVs/previous work/budget) is attached,
    the physical file must exist in the run package — a textual claim is not proof."""
    out = []
    text = _all_generated_text(ctx)
    if not text.strip():
        return out
    try:
        from .package import check_submission_package
    except Exception:
        return out
    pkg = check_submission_package(ctx["run_dir"],
                                   item_keys=["cv_annex", "previous_work", "detailed_budget"],
                                   require_proposal=False)
    present = {it["label"]: it["present"] for it in pkg["items"]}
    key_to_label = {
        "cvs": "Required CVs",
        "previous_work": "Previous-work example",
        "budget": "Financial offer / detailed budget",
    }
    for key, pat in _ANNEX_CLAIM.items():
        if pat.search(text):
            label = key_to_label[key]
            if not present.get(label, False):
                out.append(Finding("CLAIMED_ANNEX", CRITICAL, "annex_claim_without_file",
                                   f"Proposal claims '{label}' is annexed/attached, but no such "
                                   "file exists in the submission package",
                                   requirement_id="", section_id="",
                                   recommended_action=f"Add the actual {label} file to the "
                                                      "package, or remove the claim."))
    return out


# ---------------------------------------------------------------------------
# CHECK: budget reconciliation (§7/§9)
# ---------------------------------------------------------------------------

def _check_budget_reconciliation(ctx) -> list[Finding]:
    """If a structured budget exists, it must reconcile to the approved total."""
    out = []
    budget = _load(ctx["run_dir"], "budget.json")
    if not budget:
        return out
    if budget.get("missing_inputs"):
        out.append(Finding("BUDGET", CRITICAL, "budget_missing_inputs",
                           "Budget has missing line inputs: "
                           f"{', '.join(str(m) for m in budget['missing_inputs'])}",
                           section_id="BUDGET",
                           recommended_action="Collect the missing values (never invent)."))
    elif not budget.get("reconciles", False):
        out.append(Finding("BUDGET", CRITICAL, "budget_reconciliation",
                           budget.get("reconciliation_message",
                                      "Detailed budget does not reconcile to the approved total."),
                           section_id="BUDGET",
                           recommended_action="Adjust a line so the detailed budget equals "
                                              "the approved total."))
    loe = budget.get("loe_check")
    if loe and not loe.get("matches", True):
        out.append(Finding("BUDGET", WARNING, "loe_mismatch",
                           f"Budgeted person-days ({loe['budgeted_person_days']}) differ from "
                           f"approved LOE ({loe['approved_loe']}).",
                           section_id="BUDGET"))
    return out


# ---------------------------------------------------------------------------
# CHECK: current-project contamination in past experience (§5/§9)
# ---------------------------------------------------------------------------

_PAST_EXPERIENCE_SECTIONS = ("EXPERIENCE", "PAST_PERFORMANCE", "RELEVANT_EXPERIENCE",
                             "COMPANY_PROFILE", "TRACK_RECORD", "ORGANISATION",
                             "ORGANIZATIONAL_CAPACITY")


def _check_current_project_contamination(ctx) -> list[Finding]:
    """The current TOR/assignment must not be presented as past ARFADA experience."""
    out = []
    meta = (ctx["tor"] or {}).get("metadata", {})

    def mv(k):
        e = meta.get(k)
        return (e.get("value", "") if isinstance(e, dict) else "").strip()

    current_title = mv("assignment") or mv("title")
    if not current_title or len(current_title) < 8:
        return out
    cur_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", current_title.lower())}
    cur_tokens -= {"evaluation", "endline", "baseline", "midline", "final", "study",
                   "assessment", "project", "programme", "program", "survey", "review"}
    if len(cur_tokens) < 2:
        return out
    for sid, cand in ctx["gen_sections"].items():
        if not any(k in sid.upper() for k in _PAST_EXPERIENCE_SECTIONS):
            continue
        text = _section_text(cand).lower()
        hit = cur_tokens & {t for t in re.findall(r"[a-z0-9]{4,}", text)}
        if len(hit) >= max(2, len(cur_tokens) // 2):
            out.append(Finding("EXPERIENCE_CONTAMINATION", ERROR, "current_project_in_past",
                               f"Past-experience section '{sid}' appears to reference the CURRENT "
                               f"assignment (shared terms: {sorted(hit)})",
                               section_id=sid,
                               recommended_action="Remove the current assignment from past "
                                                  "experience; cite only completed work."))
    return out


# ---------------------------------------------------------------------------
# CHECK: client placeholders leaked into the client draft (§8/§9/§10)
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\[to be provided[:\]]|\[tbd\]|\[placeholder\]|\bTBD\b", re.I)


def _check_client_placeholders(ctx) -> list[Finding]:
    """The client draft must never contain '[To be provided: ...]' or similar."""
    out = []
    client_docx = ctx["run_dir"] / "proposal_client_draft.docx"
    if not client_docx.exists():
        return out
    try:
        import sys
        deps = Path(__file__).resolve().parent.parent.parent / ".mcp_deps"
        if deps.exists() and str(deps) not in sys.path:
            sys.path.insert(0, str(deps))
        from docx import Document
        doc = Document(str(client_docx))
        text = "\n".join(p.text for p in doc.paragraphs)
        for t in doc.tables:
            for row in t.rows:
                for c in row.cells:
                    text += "\n" + c.text
    except Exception:
        return out
    if _PLACEHOLDER_RE.search(text):
        out.append(Finding("CLIENT_PLACEHOLDER", CRITICAL, "client_placeholder",
                           "Client draft contains an internal placeholder "
                           "('[To be provided: ...]' / TBD) — represent the gap through the "
                           "decision/blocker system, never leak it to the client.",
                           recommended_action="Resolve the evidence gap or omit the line; "
                                              "re-render the client draft."))
    return out


# ---------------------------------------------------------------------------
# CHECK: sampling-unit mismatch + sample arithmetic (§9)
# ---------------------------------------------------------------------------

_SAMPLE_UNITS = ("households", "household", "individuals", "respondents", "people",
                 "children", "learners", "students", "women", "beneficiaries",
                 "caregivers", "facilities", "schools", "communities")


def _check_sampling(ctx) -> list[Finding]:
    """Flag a stated sample total that disagrees with the sum of its subgroups, and
    a sampling unit that is inconsistent within the same section."""
    out = []
    for sid, cand in ctx["gen_sections"].items():
        text = _section_text(cand)
        low = text.lower()
        # arithmetic: "total sample of N ( ... a ... b ... c )" where a+b+c != N
        for m in re.finditer(r"(?:total\s+)?sample(?:\s+size)?\s+of\s+(\d{2,6})", low):
            total = int(m.group(1))
            tail = low[m.end(): m.end() + 200]
            parts = [int(x) for x in re.findall(r"\b(\d{2,5})\b", tail)]
            # look for an additive breakdown that sums close to a plausible decomposition
            if len(parts) >= 2:
                s = sum(parts[:6])
                if s != total and total not in parts and abs(s - total) <= max(5, total):
                    # only flag when the parts look like a decomposition (2-6 addends)
                    if 2 <= len([p for p in parts if p < total]) <= 6 and s != total:
                        out.append(Finding("SAMPLING", ERROR, "sample_arithmetic",
                                           f"Sample total {total} in '{sid}' does not equal the "
                                           f"sum of its stated subgroups ({' + '.join(map(str, parts[:6]))} = {s})",
                                           section_id=sid,
                                           recommended_action="Reconcile the sample breakdown "
                                                              "with the stated total."))
                        break
        # unit mismatch: a single sample figure described with two different units nearby
        units_present = [u for u in _SAMPLE_UNITS if re.search(rf"\b{u}\b", low)]
        if "household" in " ".join(units_present) and \
                any(u in ("individuals", "respondents", "people") for u in units_present):
            if re.search(r"sample\s+of\s+\d", low):
                out.append(Finding("SAMPLING", WARNING, "sampling_unit_mismatch",
                                   f"'{sid}' mixes sampling units (households vs individuals) "
                                   "around the sample size — state one consistent unit.",
                                   section_id=sid, blocks_client=False))
    return out


# ---------------------------------------------------------------------------
# Repair plan (spec §32) — narrow, metadata only
# ---------------------------------------------------------------------------

def build_repair_plan(report: dict) -> dict:
    """Group repairable findings by section for a bounded regeneration."""
    by_section: dict[str, list] = {}
    for f in report["findings"]:
        if f["severity"] in (CRITICAL, ERROR) and f.get("section_id") \
                and f["check"] not in ("ARTIFACT_CONSISTENCY", "OWNERSHIP"):
            by_section.setdefault(f["section_id"], []).append({
                "finding_id": f["finding_id"], "check": f["check"],
                "message": f["message"], "recommended_action": f["recommended_action"]})
    return {
        "run_id": report["run_id"],
        "sections_to_repair": by_section,
        "max_cycles_per_section": 2,
        "note": "Repair only the listed sections; never change approved human decisions.",
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# ARFADA Final Quality Review", "",
        f"**Status: {report['overall_status']}**", "",
        f"- Mandatory requirements: {s['mandatory_addressed']}/{s['mandatory_requirements']} addressed "
        f"in the draft",
        f"- {s.get('content_line', '')}",
        f"- {s.get('evidence_line', '')}",
        f"- {s.get('readiness_line', '')}",
        f"- Critical failures: {s['critical_failures']}",
        f"- Errors: {s['errors']}",
        f"- Warnings: {s['warnings']}",
        f"- Decisions respected: {s['decisions_respected']}/{s['decisions_resolved']}",
        f"- Sections ready: {s['sections_ready']}  (blocked: {s['sections_blocked']})",
        "",
    ]
    for label, key in (("Critical Failures", "critical_failures"), ("Errors", "errors"),
                       ("Warnings", "warnings")):
        items = report.get(key, [])
        if items:
            lines.append(f"## {label} ({len(items)})")
            lines.append("")
            for f in items:
                loc = f" [{f['section_id']}]" if f["section_id"] else ""
                lines.append(f"- **{f['check']}**{loc}: {f['message']}")
                if f["recommended_action"]:
                    lines.append(f"  - _action: {f['recommended_action']}_")
            lines.append("")
    rec = ("Ready for final human review." if report["overall_status"] == "GREEN"
           else "Review warnings, then export with confirmation." if report["overall_status"] == "YELLOW"
           else "Fix critical issues before exporting a client deliverable.")
    lines += ["## Recommendation", "", rec, "",
              "> Automated QA passed does NOT replace professional human proposal review."]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CHECK: claim consistency / semantic consistency / TOR source register (v0.6.11)
# ---------------------------------------------------------------------------

def _claim_state(ctx) -> dict:
    if "_claim_state" not in ctx:
        try:
            from .claim_state import build_claim_state
            ctx["_claim_state"] = build_claim_state(ctx["run_dir"])
        except Exception:
            ctx["_claim_state"] = {}
    return ctx["_claim_state"]


def _check_claim_consistency(ctx) -> list[Finding]:
    """Definitive statements that contradict the canonical claim / package state,
    and named personnel qualifications without VERIFIED CV evidence."""
    from .claim_language import section_issues
    out = []
    state = _claim_state(ctx)
    if not state:
        return out
    for sid, cand in ctx["gen_sections"].items():
        for issue in section_issues(cand, state, section_id=sid):
            if issue.claim == "field_roster":
                continue                         # reported by the semantic check
            if issue.kind == "DURATION_WORDING":
                out.append(Finding("SOURCE_WORDING", WARNING, "duration_wording",
                                   f"Duration reworded: {issue.detail}",
                                   evidence=issue.sentence[:160], section_id=sid,
                                   blocks_client=False,
                                   recommended_action=f"Keep the TOR wording '{issue.replacement}'."))
                continue
            if issue.kind == "STAFF_NAME_NOT_CANONICAL":
                out.append(Finding("STAFF_IDENTITY", ERROR, "name_not_canonical",
                                   f"Team member not named in full: {issue.detail}",
                                   evidence=issue.sentence[:160], section_id=sid,
                                   recommended_action=f"Use the full canonical name "
                                                      f"'{issue.replacement}'."))
                continue
            if issue.kind == "PERSONNEL_UNVERIFIED":
                out.append(Finding("PERSONNEL_EVIDENCE", ERROR, "unverified_qualification",
                                   f"{issue.detail} — stated as a team qualification",
                                   evidence=issue.sentence[:160], section_id=sid,
                                   recommended_action="State only CV-verified qualifications, "
                                                      "or soften the claim."))
            else:
                out.append(Finding("CLAIM_CONSISTENCY", ERROR, "claim_contradicts_state",
                                   f"'{issue.claim}' is {issue.status} but the text states it as "
                                   "complete", evidence=issue.sentence[:160], section_id=sid,
                                   recommended_action=(f"Use: {issue.replacement}"
                                                       if issue.replacement else
                                                       "Rewrite in provisional / future language.")))
    return out


def _check_semantic_consistency(ctx) -> list[Finding]:
    """Proposal-level contradictions: Impact Evaluation vs contribution-only inference;
    a local field roster claimed without evidence."""
    from .claim_language import find_semantic_issues, find_claim_issues
    out = []
    texts = {sid: _section_text(c) for sid, c in ctx["gen_sections"].items()}
    if not texts:
        return out
    at = ctx["tor"].get("assignment_type") or {}
    labels = [str(at.get("label") or ""), str(ctx["blueprint"].get("title") or "")]
    for issue in find_semantic_issues(texts, labels=[l for l in labels if l]):
        out.append(Finding("SEMANTIC_CONSISTENCY", ERROR, "impact_vs_contribution",
                           issue.detail, evidence=issue.sentence[:160],
                           section_id=issue.section_id,
                           recommended_action="Call it an endline / final evaluation; keep "
                                              "'impact' for designs with causal attribution."))
    state = _claim_state(ctx)
    roster_only = {"claims": {"field_roster": (state.get("claims") or {}).get("field_roster", {})}}
    for sid, text in texts.items():
        for issue in find_claim_issues(text, roster_only, section_id=sid):
            out.append(Finding("SEMANTIC_CONSISTENCY", ERROR, "roster_claim_without_evidence",
                               f"Local field roster claimed but roster evidence is "
                               f"{issue.status}", evidence=issue.sentence[:160], section_id=sid,
                               recommended_action=f"Use: {issue.replacement}"))
    return out


def _check_qualification_wording(ctx) -> list[Finding]:
    """v0.6.15: client-facing qualification claims never stronger than EVIDENCE_STATUS.

    Rewritable overclaims (blanket "met by the team collectively", a "how the team covers
    it" column, a methodological commitment shown as team coverage) are warnings — the
    final-language sanitizer rewrites them for export. A not-evidenced qualification
    attributed to a named expert / role is a personnel-evidence error."""
    from .qualification_wording import find_qualification_issues
    out = []
    state = _claim_state(ctx)
    if not state.get("requirement_evidence"):
        return out
    for sid, cand in ctx["gen_sections"].items():
        for it in find_qualification_issues(cand, state, section_id=sid):
            if it["kind"] == "UNEVIDENCED_PERSONNEL_CLAIM":
                out.append(Finding("PERSONNEL_EVIDENCE", ERROR, "unevidenced_qualification_claim",
                                   it["detail"], evidence=it["sentence"][:160], section_id=sid,
                                   recommended_action="State it as a methodological provision, or "
                                                      "promote the CV evidence (staff fact)."))
            else:
                out.append(Finding("QUALIFICATION_CLAIM", WARNING, it["kind"].lower(),
                                   f"Qualification claim stronger than the evidence: {it['detail']}",
                                   evidence=it["sentence"][:160], section_id=sid,
                                   blocks_client=False,
                                   recommended_action=(f"Use: {it['replacement'][:160]}"
                                                       if it.get("replacement") else
                                                       "Remove internal labels from proposal text.")))
    return out


def _check_source_semantics(ctx) -> list[Finding]:
    """v0.6.13: TOR TARGET figures called 'registered'; target-derived stratum allocations
    not marked provisional (to be recalculated at inception from the registration list)."""
    from .source_semantics import find_population_issues
    out = []
    register = _claim_state(ctx).get("population_figures") or {}
    if not register.get("figures"):
        return out
    for sid, cand in ctx["gen_sections"].items():
        for it in find_population_issues(cand, register, section_id=sid):
            if it["kind"] == "REGISTERED_TARGET_FIGURE":
                msg, act = (f"TOR target figure written as registered: {it['detail']}",
                            "Call it the TOR target composition; 'registered' needs a "
                            "registration record (project_records.json).")
            else:
                msg, act = (f"Allocation not marked provisional: {it['detail']}",
                            "Write: Provisional allocation based on the TOR target composition; "
                            "recalculated at inception from the registration list.")
            out.append(Finding("SOURCE_SEMANTICS", WARNING, it["kind"].lower(), msg,
                               evidence=it["sentence"][:160], section_id=sid,
                               blocks_client=False, recommended_action=act))
    return out


def _check_requirement_evidence(ctx) -> list[Finding]:
    """v0.6.14: mandatory qualifications the selected team does not (fully) evidence.

    EVIDENCE_STATUS is independent of RESPONSE_STATUS: the text may answer a
    qualification (ADDRESSED) while ARFADA lacks proof (PARTIAL / GAP). These are
    reported for internal review with QUALIFICATION_READINESS (PARTIAL / AT_RISK) and
    never block the technical draft."""
    from .requirement_evidence import QUALIFICATION_TYPES, EV_PARTIAL, EV_GAP
    out = []
    for r in _coverage_rows(ctx):
        if r["requirement_type"] not in QUALIFICATION_TYPES or not r.get("mandatory", True):
            continue
        if r["evidence_status"] not in (EV_PARTIAL, EV_GAP):
            continue
        gaps = ", ".join(r.get("gaps") or []) or "evidence"
        out.append(Finding("REQUIREMENT_EVIDENCE", INFO,
                           f"evidence_{r['evidence_status'].lower()}",
                           f"Qualification {r['qualification_readiness']} (evidence "
                           f"{r['evidence_status']}, text {r['response_status']}): "
                           f"{r['text'][:90]} — not evidenced by the selected team: {gaps}",
                           evidence=r.get("basis", ""), requirement_id=r["req_id"],
                           section_id="TEAM", blocks_client=False,
                           recommended_action="Promote the CV evidence (staff fact) if it exists, "
                                              "or strengthen the team; keep the methodology "
                                              "commitment separate from the qualification."))
    return out


def _coverage_rows(ctx) -> list:
    """Per requirement: RESPONSE_STATUS (computed from the text) + EVIDENCE_STATUS
    (computed from CV / company / claim-state provenance) + QUALIFICATION_READINESS."""
    if "_coverage_rows" not in ctx:
        from .requirement_evidence import evidence_matrix
        from .response_coverage import combine
        state = _claim_state(ctx)
        matrix = state.get("requirement_evidence")
        if matrix is None:
            matrix = evidence_matrix(ctx["requirements"], state.get("team") or [],
                                     claims=state.get("claims") or {})
        ctx["_coverage_rows"] = combine(matrix, _responses(ctx))
    return ctx["_coverage_rows"]


def _check_source_inconsistency(ctx) -> list[Finding]:
    """TOR figures / wording that do not reconcile — logged, never silently corrected."""
    out = []
    data = _load(ctx["run_dir"], "source_inconsistencies.json") or {}
    for it in data.get("items", []):
        out.append(Finding("SOURCE_INCONSISTENCY", INFO, it.get("type", "source").lower(),
                           f"TOR source inconsistency: {it.get('detail', '')}",
                           evidence=str(it.get("excerpt", ""))[:160], blocks_client=False,
                           recommended_action="Reproduce the TOR values unchanged and state they "
                                              "will be reconciled against the approved baseline "
                                              "dataset and PMF during inception."))
    return out
