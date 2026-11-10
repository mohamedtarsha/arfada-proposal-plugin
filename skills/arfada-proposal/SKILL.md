---
name: arfada-proposal
description: >
  ARFADA Proposal Assistant — TOR analysis, human decision review, controlled
  draft generation, and professional Word export for ARFADA team members. Invoke
  with /arfada-proposal to analyze a TOR, review decisions, generate, or export.
version: 0.5.2
trigger: /arfada-proposal
---

# ARFADA Proposal Assistant

**Plugin version:** 0.5.2
**Publisher:** ARFADA
**Status:** Phase 4.2 — Local / synced knowledge folder + Professional DOCX active

---

## Menu

When invoked without context, print:

```
ARFADA Proposal Assistant v0.5.2

Available now:
  1. Analyze TOR               — provide a .pdf or .docx file
  2. Review Proposal Decisions — review and record proposal choices
  3. Refresh ARFADA Knowledge  — scan the local ARFADA Knowledge folder
  4. Generate Proposal Draft   — build a TOR-grounded draft section by section
  5. Export Word               — professional DOCX (internal review / client draft)

Coming later:
  6. Final Quality Review

Also: "Set ARFADA Knowledge Folder", "ARFADA Knowledge Status"
```

If a run directory is already in context (from previous analysis), offer the
relevant next step with `[run: <run_id>]`.

---

## ARFADA Knowledge (local / synced folder — PRIMARY, OAuth-free)

ARFADA operational data lives in a single **local folder** the user picks. It may be
a plain folder or a **Google Drive for Desktop / OneDrive / Dropbox / network-mounted**
folder — the plugin only sees a filesystem path and calls **no cloud API**. No OAuth,
no VPS, no MCP server, no Anthropic API. Recommended layout:

```
ARFADA Knowledge/
├── Projects/Master Tracker.xlsx
├── Staff CVs/<Country>/*.pdf|*.docx
├── Company/...
└── Brand/<logo>.png
```

### Set / show / change the folder
```bash
python "<plugin_root>/scripts/knowledge_folder.py" set "C:/Users/<you>/ARFADA Knowledge"
python "<plugin_root>/scripts/knowledge_folder.py" show
python "<plugin_root>/scripts/knowledge_folder.py" clear
```
Stored under `%USERPROFILE%/.arfada-proposal/` (never in the repo).

### Refresh (incremental, transactional)
```bash
python "<plugin_root>/scripts/refresh_knowledge.py"
```
Scans the folder: reads `Master Tracker.xlsx` (deterministic metrics), recursively
indexes CVs (country from subfolder), company docs, and the brand logo. Only new/
changed files are reprocessed; a failed refresh keeps the previous valid cache.
Cloud-placeholder files not physically downloaded are reported
`FILE_NOT_AVAILABLE_LOCALLY` and skipped safely. Example summary:
```
Projects: 148  Countries: 9  CVs indexed: 63  Company files: 12
Logo: found   Updated files: 4   Warnings: 1
```

### Status
```bash
python "<plugin_root>/scripts/knowledge_status.py"
```
Shows: source_mode (**LOCAL_FOLDER** / GOOGLE_API / STATIC_FALLBACK), knowledge root,
last refresh, freshness (FRESH <24h / WARNING 1–7d / STALE >7d), project/CV/company
counts, logo availability, static fallback version.

### Source priority
1. frozen run knowledge snapshot
2. **LOCAL_FOLDER** (default recommended)
3. Google API connector (OPTIONAL / ADVANCED — `connect_google.py`; not required)
4. STATIC_FALLBACK (only when nothing else is configured; never implied as current)

### Staleness / offline
If `freshness` is STALE, ask the user to refresh before generating. Because files are
local, normal use works offline. If never configured, state:
> "ARFADA KNOWLEDGE SOURCE: STATIC FALLBACK — set your local ARFADA Knowledge folder."

### Proposal-time snapshot (automatic, immutable)
`build_blueprint.py` freezes the relevant knowledge into
`arfada-output/<run_id>/knowledge_snapshot/` with a manifest (snapshot_id,
source_mode=LOCAL_FOLDER, Master Tracker file hash + modified time, staff/company
revisions, plugin_version). That run uses its **frozen** snapshot — changing a file
afterward does NOT alter an in-flight proposal; only future runs (or an explicit
re-freeze) see new data. Local filesystem paths are NEVER written into client DOCX.

### Google API connector — optional/advanced
The OAuth connector (`connect_google.py`, `sync_google_knowledge.py`) still exists but
is NOT required. Prefer the local folder (works offline, no credentials).

### Staff (personnel) — suggestions only
`knowledge.search_staff(country, role, min_years, language)` returns candidate CVs
(hard qualification constraints filter; soft factors rank). **Suggested ≠ approved.**
Present candidates, let the user choose, record the approved `staff_id` in the
Decision Register before generation uses that person's facts. Never invent staff
names — use "To be nominated".

---

## Assignment type (shown after Analyze TOR)

`tor_analysis.json` now carries `assignment_type` with confidence + evidence.
After analysis, show:

```
Assignment Type: <label>
Confidence:      <HIGH|MEDIUM|LOW>
Evidence:        <evidence snippets>
```

If confidence is LOW, `decision_candidates.json` contains a `dec_assignment_type`
decision. Resolve it in Decision Review BEFORE building a type-dependent blueprint —
never silently assume Evaluation. The user picks from `allowed_options` (or OTHER).

## ARFADA knowledge (verified facts)

Generation packets now include `verified_arfada_facts` — the ONLY ARFADA
organizational facts you may state (each has a `fact_id` + provenance). Numbers
come from these facts, never recomputed. To show them on request:
```bash
python "<plugin_root>/scripts/query_knowledge.py" metrics
python "<plugin_root>/scripts/query_knowledge.py" search --type EVALUATION --country Lebanon
```
Any ARFADA claim NOT backed by a verified fact → use a `NEEDS_ARFADA_EVIDENCE`
placeholder. The validator rejects unsupported ARFADA claims (`UNSUPPORTED_ARFADA_CLAIM`).

---

## CRITICAL: You are the generator

In Phase 3, **you (the active Claude Code session) write the proposal content**.
There is NO separate API call. The Python scripts are deterministic plumbing:
they build packets, validate your output, and persist artifacts. You must:
- read each generation packet
- write a structured section candidate JSON following the packet's output_contract
- never bypass the packet or invent facts outside TOR + approved decisions

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

## Constraints (Decision Review)

- NEVER auto-resolve a decision without explicit user confirmation.
- NEVER modify TOR-fixed requirements (they don't appear in the decision register).
- NEVER invent TOR constraints not in decision_candidates.json.
- If the run directory changes (different TOR), start a new analysis — do not apply decisions cross-TOR.
- Output directories (arfada-output/) are local only.

---

## 3. Generate Proposal Draft

### Step 1 — Build the blueprint

```bash
python "<plugin_root>/scripts/build_blueprint.py" "<run_dir>"
```

This reads tor_analysis.json + requirements.json + decision_register.json (if present),
validates run identity, and writes proposal_blueprint.json + generation_status.json.

Present the blueprint summary to the user:

```
Proposal Blueprint

Sections:                     [sections]
Mandatory requirements:       [mandatory_bidder_requirements]
Response slots:               [response_slots]
Open decisions:               [open_decisions]
Sections blocked by decisions:[sections_blocked_by_decisions]
Sections needing ARFADA evidence: [sections_needing_evidence]

Section order: [section_order list]
```

If `open_decisions > 0`, note:
> Some sections depend on unresolved decisions and will be marked BLOCKED.
> You can resolve them first (option 2) or generate the unblocked sections now.

### Step 2 — Generate sections one at a time

Loop until no PENDING sections remain:

**a.** Find the next section:
```bash
python "<plugin_root>/scripts/generation_status.py" "<run_dir>" --next
```
If `next_section` is null → go to Step 3 (assemble).

**b.** Prepare the packet:
```bash
python "<plugin_root>/scripts/prepare_section.py" "<run_dir>" "<section_id>"
```
If the response status is `BLOCKED_BY_DECISION`, mark it and move on (the script
already set the status). Otherwise the full packet is printed.

**c.** Read the packet. **Write the section candidate yourself** following the
packet's `output_contract`. Produce a JSON object:
```json
{
  "section_id": "<section_id>",
  "blocks": [
    {"block_id": "b1", "type": "paragraph", "text": "..."},
    {"block_id": "b2", "type": "bullet_list", "items": ["...", "..."]},
    {"block_id": "b3", "type": "table", "columns": ["...","..."], "rows": [["...","..."]]}
  ],
  "requirement_response_ledger": [
    {"slot_id": "<from mandatory_slots>", "requirement_id": "<...>",
     "block_ids": ["b1"], "response_summary": "...", "status": "ADDRESSED"}
  ]
}
```

Rules you MUST follow when writing:
- Every mandatory slot in the packet needs a ledger entry with real block_ids.
- Use `applied_decisions` values EXACTLY (e.g. if KII count resolved to 35, write 35 — never 30 or "approximately 35").
- For DEFERRED decisions, state confirmation at inception; do NOT invent a value.
- For sections with `needs_arfada_evidence: true`, use an `evidence_placeholder`
  block with text `NEEDS_ARFADA_EVIDENCE: <what is needed>` instead of inventing
  organizational facts (years, project counts, past clients, staff names).
- Prefer tables for EVALUATION_FRAMEWORK, DELIVERABLES, WORKPLAN, TEAM.
- Keep paragraphs 60–120 words. Respond substantively — do not just restate the TOR.
- EXECUTIVE_SUMMARY is generated LAST (the status script enforces order).

Write the candidate to `<run_dir>/_candidate_<section_id>.json` using the Write tool.

**d.** Validate + persist:
```bash
python "<plugin_root>/scripts/validate_section.py" "<run_dir>" "<section_id>" "<run_dir>/_candidate_<section_id>.json"
```
- Exit 0 / status READY → section persisted. Continue to next section.
- Exit 4 / status INVALID → read the errors + failed_slots. Fix ONLY those,
  rewrite the candidate, and re-run validate. Maximum **2 repair attempts**
  (the script enforces the cap and marks FAILED after that).

### Step 3 — Assemble the draft

```bash
python "<plugin_root>/scripts/assemble_draft.py" "<run_dir>"
```

Present the coverage summary:
```
Proposal Draft Assembled — proposal_draft.md

Sections ready:    [sections_ready]
Sections blocked:  [sections_blocked]

Requirement coverage:
  Addressed:                   [addressed]
  Partial:                     [partial]
  Missing:                     [missing]
  Blocked by decision:         [blocked_by_decision]
  Blocked by missing evidence: [blocked_by_missing_evidence]
```

Then offer:
```
  show draft          — display proposal_draft.md
  resume              — generate any remaining unblocked sections
  review decisions    — resolve blocking decisions, then regenerate
  done
```

### Resume behavior

Re-entering "Generate Proposal Draft" on an existing run detects state via
generation_status.json. Do NOT regenerate READY sections unless the user
explicitly asks. Continue from the next PENDING section.

---

## Constraints (Generation)

- You are the generator — no separate API. Write section candidates yourself.
- Allowed facts: TOR + approved Decision Register + `verified_arfada_facts` ONLY.
- NEVER invent ARFADA organizational facts — use NEEDS_ARFADA_EVIDENCE placeholders.
- You MAY state a `verified_arfada_facts` value (reference the fact_id in your summary).
- NEVER contradict a TOR-fixed value or an approved decision value.
- NEVER invent a value for an unresolved/deferred decision.
- For the type-specific FRAMEWORK section, the matrix table columns MUST equal
  `output_contract.required_table_columns`.
- TEAM: never invent staff names — use "To be nominated"; preserve TOR qualification constraints.
- No historical proposal text, no RAG, no web research in this phase.
- Max 2 repair attempts per section; respect the validator's verdict.
- Generated drafts (arfada-output/) are local only — never committed.

---

## 4. Export Word

After generation, offer two professional DOCX exports.

### Internal review document
```bash
python "<plugin_root>/scripts/render_docx.py" "<run_dir>" --internal
```
Shows NEEDS_ARFADA_EVIDENCE placeholders, BLOCKED_BY_DECISION notes, and a
version/knowledge footer. For the ARFADA team.

### Client draft document
```bash
python "<plugin_root>/scripts/render_docx.py" "<run_dir>" --client
```
Hides all internal IDs, fact_ids, and system notes. If unresolved evidence gaps
remain, it is marked "DRAFT — HUMAN REVIEW REQUIRED". If a section has a hard
unsupported-fact error, **client export fails** (exit 5) — fix the section first.

Optional logo: add `--logo "<path to ARFADA logo.png>"` for the cover page.

Present the result:
```
Word export complete — proposal_<variant>.docx

Sections rendered: X   Blocked: Y
Paragraphs: P   Tables: T   Lists: L   Headings: H
Pre-export QA: <ok|warnings>
```

### Pre-export QA
`render_docx.py` runs a deterministic pre-export check first (schema re-validation,
decision values, unsupported facts, cross-TOR, client-leakage). Warnings are shown
but do not block internal export; hard errors block both; unsupported-fact errors
block client export.

---

## Constraints (Export)

- DOCX is generated with python-docx only — no MS Word automation, no LibreOffice.
- Client export must never expose internal IDs, fact_ids, or system metadata.
- Never fabricate the ARFADA logo; use `--logo` only with an authorized local file.
- Every exported proposal records plugin_version + knowledge_version + run_id (internal).
- Generated DOCX (arfada-output/) is local only — never committed.
