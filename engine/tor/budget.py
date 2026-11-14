"""Interactive budget builder + reconciliation (v0.6.4, production hardening §7).

Builds a detailed budget from an APPROVED total and APPROVED level of effort (LOE)
plus line inputs the user supplies interactively (daily rates, field supervisor,
enumerators, transport, participant reimbursement, translation/transcription,
editing/printing, taxes/mandatory costs, other TOR-specific costs).

Rules:
  * Never invents a value — a line with no usable input is reported as MISSING_INPUT.
  * Every line amount is computed deterministically (quantity × unit_cost, or a
    percentage of a base for taxes/overheads, or an explicit amount).
  * The detailed budget must reconcile EXACTLY to the approved total (within an
    optional rounding tolerance); the reconciliation is shown before approval.
No model call, no network.
"""
from __future__ import annotations

from typing import Any, Optional

# Canonical line categories (for ordering + the interactive prompt order).
CATEGORIES = [
    "expert_fees", "field_supervisor", "enumerators", "transport",
    "participant_reimbursement", "translation_transcription",
    "editing_printing", "taxes_mandatory", "other",
]


def _round(x: float) -> float:
    return round(float(x) + 1e-9, 2)


def compute_line(line: dict, *, subtotal: Optional[float] = None) -> dict:
    """Compute one line's amount. Returns a copy with `amount` and `status`.

    Input forms (no invention):
      - explicit amount:            {"amount": 1200}
      - quantity × unit_cost:       {"quantity": 10, "unit_cost": 120}
      - percent of a base/subtotal: {"percent": 16, "base": 5000}  (base optional → subtotal)
    """
    out = dict(line)
    label = line.get("label") or line.get("category") or "line"
    amount = None
    if line.get("amount") is not None:
        amount = _round(line["amount"])
        out["basis"] = "explicit"
    elif line.get("percent") is not None:
        base = line.get("base")
        if base is None:
            base = subtotal
        if base is None:
            out["status"] = "MISSING_INPUT"
            out["amount"] = None
            out["note"] = f"'{label}': percent line needs a base (no subtotal available)."
            return out
        amount = _round(float(base) * float(line["percent"]) / 100.0)
        out["basis"] = f"{line['percent']}% of {_round(base)}"
    elif line.get("quantity") is not None and line.get("unit_cost") is not None:
        amount = _round(float(line["quantity"]) * float(line["unit_cost"]))
        out["basis"] = f"{line['quantity']} × {line['unit_cost']}"
    else:
        out["status"] = "MISSING_INPUT"
        out["amount"] = None
        out["note"] = (f"'{label}': provide amount, or quantity+unit_cost, or percent. "
                       "No value will be invented.")
        return out
    out["amount"] = amount
    out["status"] = "OK"
    return out


def build_budget(*, approved_total: float, lines: list[dict],
                 approved_loe: Optional[float] = None, currency: str = "USD",
                 tolerance: float = 0.0) -> dict:
    """Assemble + reconcile a detailed budget against the approved total.

    Two-pass: fixed/quantity/explicit lines first (subtotal), then percent lines
    (taxes/overheads) against that subtotal. Returns the full structured budget
    with a reconciliation block to show BEFORE approval.
    """
    approved_total = _round(approved_total)
    # pass 1: non-percent lines establish the subtotal; defer percent-of-subtotal lines.
    computed: list[Optional[dict]] = [None] * len(lines)
    percent_idx: list[int] = []
    subtotal = 0.0
    for i, ln in enumerate(lines):
        if ln.get("percent") is not None and ln.get("amount") is None and ln.get("base") is None:
            percent_idx.append(i)  # resolved in pass 2 against the subtotal
            continue
        c = compute_line(ln)
        computed[i] = c
        if c.get("status") == "OK":
            subtotal += c["amount"]
    subtotal = _round(subtotal)
    # pass 2: percent-of-subtotal lines (taxes/overheads)
    for i in percent_idx:
        computed[i] = compute_line(lines[i], subtotal=subtotal)
    computed = [c for c in computed if c is not None]

    missing = [c for c in computed if c.get("status") == "MISSING_INPUT"]
    total = _round(sum(c["amount"] for c in computed if c.get("status") == "OK"))
    difference = _round(total - approved_total)
    reconciles = (not missing) and abs(difference) <= (tolerance + 1e-9)

    loe_check = None
    if approved_loe is not None:
        expert_days = _round(sum(
            float(ln.get("quantity") or 0)
            for ln in lines if ln.get("category") in ("expert_fees", "field_supervisor",
                                                       "enumerators")))
        loe_check = {
            "approved_loe": _round(approved_loe),
            "budgeted_person_days": expert_days,
            "matches": abs(expert_days - _round(approved_loe)) <= 1e-9,
        }

    return {
        "currency": currency,
        "approved_total": approved_total,
        "approved_loe": approved_loe,
        "lines": computed,
        "subtotal": subtotal,
        "computed_total": total,
        "difference": difference,
        "reconciles": reconciles,
        "missing_inputs": [c.get("label") or c.get("category") for c in missing],
        "loe_check": loe_check,
        "reconciliation_message": _reconciliation_message(total, approved_total, difference,
                                                          reconciles, missing, currency),
    }


def _reconciliation_message(total, approved_total, difference, reconciles, missing,
                            currency) -> str:
    if missing:
        names = ", ".join(str(m) for m in
                          [c.get("label") or c.get("category") for c in missing])
        return (f"Cannot reconcile — missing inputs for: {names}. "
                "Ask the user for these values (never invent).")
    if reconciles:
        return (f"Reconciled: detailed budget {currency} {total:,.2f} "
                f"= approved total {currency} {approved_total:,.2f}.")
    sign = "over" if difference > 0 else "under"
    return (f"Does NOT reconcile — detailed budget {currency} {total:,.2f} is "
            f"{currency} {abs(difference):,.2f} {sign} the approved total "
            f"{currency} {approved_total:,.2f}. Adjust a line before approval.")
