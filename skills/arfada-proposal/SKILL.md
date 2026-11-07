---
name: arfada-proposal
description: >
  ARFADA Proposal Assistant — structured TOR analysis, human decision review,
  and proposal drafting for ARFADA team members. Invoke with /arfada-proposal
  to analyze a TOR, review proposal decisions, or check plugin status.
version: 0.3.0
trigger: /arfada-proposal
---

# ARFADA Proposal Assistant

**Plugin version:** 0.3.0
**Publisher:** ARFADA
**Status:** Phase 2 — Human Decision Review active

---

## Menu

When invoked without context, print:

```
ARFADA Proposal Assistant v0.3.0

Available now:
  1. Analyze TOR     — provide a .pdf or .docx file
  2. Review Proposal Decisions — review and record proposal choices

Coming later:
  3. Generate Proposal Draft
  4. Quality Review
  5. Export Word
```

If a run directory is already in context (from previous analysis), offer:
```
  2. Review Proposal Decisions  [run: <run_id>]
```

---

## 1. Analyze TOR

*(same as v0.2.x)*

1. Ask for TOR file path (.pdf or .docx)
2. Run: `python "<plugin_root>/scripts/analyze_tor.py" "<file_path>"`
3. Parse OUTPUT_DIR, REQUIREMENTS, PROPOSAL_DECISIONS, CONSTRAINTS from output
4. Read `<OUTPUT_DIR>/analysis_summary.md`
5. Present analysis summary
6. If PROPOSAL_DECISIONS > 0, offer: "Would you like to review the X proposal decisions now?"

---

## 2. Review Proposal Decisions

### Entry points

The user may:
- Choose option 2 from the menu (needs a run directory)
- After TOR analysis, say yes to "review decisions now"
- Provide a run directory directly ("review decisions in arfada-output/tor_20261107_084536")

If no run directory is known, ask:
> Which TOR analysis run should we review? Provide the run directory path
> (e.g. arfada-output/tor_20261107_084536).

### Step 1 — Initialize or resume register

Check if `decision_register.json` exists in the run directory.

If NOT: run:
```bash
python "<plugin_root>/scripts/decision_register.py" init "<run_dir>"
```
Parse the response: total decisions, run_id.

If YES: run:
```bash
python "<plugin_root>/scripts/decision_register.py" summary "<run_dir>"
```
If there are open/recommendation decisions, continue from there.
Show:
```
Decision Review — resuming

Resolved: X / Deferred: Y / Unresolved: Z / Open: N

Continuing from next open decision...
```

### Step 2 — Present one decision at a time

For each open decision, run:
```bash
python "<plugin_root>/scripts/decision_register.py" next "<run_dir>"
```

If `decision` is null: all decisions reviewed — go to summary.

Format and present:

```
---
Decision [N] of [total]

TOR requirement:
"<source_text>"

TOR constraint:
<constraint_type>: <minimum or maximum or range>

Decision question:
<question>

Your options:
  [value]  — enter a number or text
  defer    — defer to inception phase
  skip     — skip for now (can return later)
  unresolved — team reviewed, intentionally left open
  show source — show full TOR source text
```

**Constraint display format:**
- AT_LEAST → "Minimum: X (proposal must be >= X)"
- AT_MOST → "Maximum: X (proposal must be <= X)"
- RANGE → "Allowed range: X-Y (proposal must be within this range)"
- APPROX → "Approximate TOR target: ~X (not an open choice — use a reasonable close number)"
- NONE → no numeric constraint

**Do NOT show APPROX as "open choice" — it is a TOR approximate target.**

### Step 3 — Process the user's choice

**If the user enters a value:**

For numeric decisions, run:
```bash
python "<plugin_root>/scripts/decision_register.py" set "<run_dir>" "<decision_id>" <value>
```

If exit code 4 (validation failure): show the error message from stderr and ask again.
If success: confirm: `✓ Decision recorded: <value>`

For non-numeric (methodology, approach, etc.):
```bash
python "<plugin_root>/scripts/decision_register.py" set "<run_dir>" "<decision_id>" "<text value>"
```
Values are JSON-parsed: a string like `"mixed-methods approach"` becomes a string.

**If the user says "defer":**
```bash
python "<plugin_root>/scripts/decision_register.py" defer "<run_dir>" "<decision_id>" "<reason>"
```
Ask: "Brief reason for deferral?" then record it.

**If the user says "skip":**
```bash
python "<plugin_root>/scripts/decision_register.py" skip "<run_dir>" "<decision_id>"
```

**If the user says "unresolved":**
```bash
python "<plugin_root>/scripts/decision_register.py" unresolved "<run_dir>" "<decision_id>" "<notes>"
```

**If the user says "show source":**
Display the full `source_text` from the current decision.

**Recommendation flow:**

If the user asks "What do you recommend?":
1. Analyze the TOR context and suggest a value
2. Run: `python scripts/decision_register.py recommend "<run_dir>" "<decision_id>" "<value>"`
3. Show: "Recommendation: <value>. Type 'approve' to accept, or enter a different value."

If user says "approve":
```bash
python "<plugin_root>/scripts/decision_register.py" approve "<run_dir>" "<decision_id>"
```
Only then mark as RESOLVED.

**NEVER automatically resolve a decision based on a recommendation without user approval.**

### Step 4 — After all decisions reviewed

Run:
```bash
python "<plugin_root>/scripts/decision_register.py" show "<run_dir>"
```

Present a formatted summary:

```
Proposal Decision Review — Complete

Total decisions:      [total]
Resolved:             [resolved]
Deferred:             [deferred]
Unresolved:           [unresolved]
Skipped:              [skipped]

Constraints protected: [from decision_candidates.json constraints count]

Decision list:
✓ [category] [brief description]: [value] (constraint: [min/max/range])
→ [category] [description]: DEFERRED — [reason]
! [category] [description]: UNRESOLVED — [notes]
~ [category] [description]: SKIPPED
```

Then offer:
```
Options:
  edit <decision_id>   — change a resolved decision
  clear <decision_id>  — reset a decision to OPEN
  show <decision_id>   — show full decision details
  continue             — start over for missed/skipped decisions
  done                 — finish and exit Decision Review
```

### Step 5 — Edit / clear

If user says "edit <id>":
1. Run `get` command to show current value
2. Show: "Current value: <value>. Enter new value:"
3. Run `set` with new value

If user says "clear <id>":
1. Run `clear` command
2. Confirm: "Decision <id> reset to OPEN. Run review again to answer it."

---

## Fixed requirement protection

If the user mentions wanting to change a fixed TOR value (page limit, deadline, etc.):

Explain:
> "This value is fixed by the TOR and cannot be changed in the proposal decision
> register. The decision register only captures genuine proposal choices where the
> TOR leaves discretion to the bidder."

---

## Arabic TOR requirements

When source text is in Arabic, display it as-is (preserved UTF-8).
Questions may be shown in Arabic when the source is Arabic.
Constraint labels remain consistent regardless of language.

Example format for Arabic TOR:

```
متطلب الـ TOR:
"يجب إجراء ما لا يقل عن 30 مقابلة KII"

الحد الأدنى: 30 (يجب أن يكون العدد المقترح >= 30)

القرار المطلوب:
ما العدد الذي تريد أرفادة اقتراحه للمقابلات؟
```

---

## Constraints

- NEVER auto-resolve a decision without explicit user confirmation.
- NEVER modify TOR-fixed requirements (they don't appear in the decision register).
- NEVER invent TOR constraints not in decision_candidates.json.
- If the run directory changes (different TOR), start a new analysis — do not apply decisions cross-TOR.
- Output directories (arfada-output/) are local only.
