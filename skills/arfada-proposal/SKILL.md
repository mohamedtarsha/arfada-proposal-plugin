---
name: arfada-proposal
description: >
  ARFADA Proposal Assistant — TOR analysis, human decision review, controlled
  draft generation, and professional Word export for ARFADA team members. Invoke
  with /arfada-proposal to analyze a TOR, review decisions, generate, or export.
version: 0.6.3
trigger: /arfada-proposal
---

# ARFADA Proposal Assistant

**Plugin version:** 0.6.4
**Publisher:** ARFADA
**Status:** Complete + Writing DNA + Production Workflow — init → TOR → decisions →
knowledge → generation → budget → DOCX → Final QA → package → export

---

## Menu

When invoked without context, print:

```
ARFADA Proposal Assistant v0.6.4

  0. Run Initialization        — verify knowledge, DNA, historical pairs, versions
  1. Analyze TOR               — provide a .pdf or .docx file
  2. Review Proposal Decisions — review and record proposal choices
  3. Refresh ARFADA Knowledge  — scan the local ARFADA Knowledge folder
  4. Generate Proposal Draft   — build a TOR-grounded draft section by section
  5. Export Word               — professional DOCX (internal review / client draft)
  6. Final Quality Review      — deterministic GREEN/YELLOW/RED acceptance + gated final

Also: "Set ARFADA Knowledge Folder", "ARFADA Knowledge Status"
```

If a run directory is already in context (from previous analysis), offer the
relevant next step with `[run: <run_id>]`.

---

## Default proposal workflow (v0.6.4 — productionized)

Follow this order by default so each TOR needs far less manual intervention. Every
step is deterministic Python; the active session handles conversation and content.

0. **Run initialization** — `run_init.py` (verify sources, DNA, pairs, versions).
1. **Analyze TOR** — `analyze_tor.py` (requirements, metadata, decisions, type).
2. **Submission checklist** — `submission_checklist.py` (MANDATORY / SCORING / OPTIONAL
   with real item identities).
3. **Review proposal decisions** — native option cards, one at a time (§ "2. Review…").
4. **Relevant experience** — `relevant_experience.py` ranks past assignments
   (current project excluded); user selects the final 3–5 via cards.
5. **Interactive budget** — `budget_builder.py` collects rates/LOE, reconciles to the
   approved total before approval.
6. **Generate draft** — evidence-first; promote any CV-read fact to a structured
   staff fact before use.
7. **Export internal / client** — client draft never carries internal markers or
   `[To be provided: ...]`.
8. **Final Quality Review** — `final_qa.py` (GREEN/YELLOW/RED).
9. **Submission package check** — `submission_package.py` (physical files exist).
10. **Final export** — `export_final.py` (gated + sanitized).

---

## 0. Run Initialization

At the start of EVERY new TOR run, verify and report the environment — do NOT
re-index or regenerate anything (Writing DNA + exemplars persist across sessions and
are auto-discovered):

```bash
python "<plugin_root>/scripts/run_init.py" --compact
```

Show the compact summary, e.g.:

```
Knowledge: ACTIVE
Master Tracker: ACTIVE
Staff CVs: ACTIVE
Writing DNA: ACTIVE
Historical pairs: 14
Previous Work library: ACTIVE
Plugin: v0.6.4 · Knowledge snapshot: 2026.11.1
```

If a source is INACTIVE, offer the one-line fix (set the Knowledge folder; set the
Winning Proposal Library) — but never block analysis on it. Use `run_init.py` (no
`--compact`) for the full JSON when the user asks for detail.

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

## Winning Proposal Library (ARFADA Writing DNA — STYLE ONLY)

A separate local folder of **past winning proposals** teaches ARFADA's human writing
style, structure, formatting, and TOR→response patterns. It is **STYLE guidance only**
— never a factual source. Strict separation:
- **Facts** (Master Tracker / CVs / company / TOR / decisions) — authoritative
- **Historical proposals** — style/structure/response-pattern exemplars only, LOWEST authority

Historical content NEVER becomes a current fact (counts, staff, clients, dates, metrics)
and must NEVER be copied verbatim — the validator + Final QA run an anti-copy guard.

### Set / show / clear
```bash
python "<plugin_root>/scripts/exemplar_library.py" set "C:/Users/<you>/Firass's Proposals"
python "<plugin_root>/scripts/exemplar_library.py" show
python "<plugin_root>/scripts/exemplar_library.py" clear
```

### Refresh + status
```bash
python "<plugin_root>/scripts/refresh_exemplars.py"            # scan → index + Writing DNA
python "<plugin_root>/scripts/refresh_exemplars.py" --status   # library status
```
Recursively discovers `Country/Project/{TOR, Proposal}`, pairs them (ambiguous pairs
excluded), extracts section exemplars + Writing/Formatting DNA + response patterns.
Prefers DOCX, no OCR, scanned docs warn. Status shows configured path, projects, valid
pairs, ambiguous pairs, countries, assignment types, last refresh, warnings. Everything
is LOCAL (gitignored) — no corpus content is ever committed or printed.

### How it influences generation (automatic, bounded)
When a library is configured, each generation packet gains (at LOWEST authority):
- `style_guidance.writing_dna` — corpus paragraph length, table/bullet usage, voice, guidance
- `style_guidance.response_patterns` — how ARFADA answers requirements (rationale, respondents,
  triangulation, analysis) — reproduce the REASONING pattern, never the wording
- `historical_exemplars` — top-3 section-specific bounded excerpts (methodology exemplars for
  METHODOLOGY, workplan for WORKPLAN, etc.)

Use these to write in ARFADA's specific, human style and reduce generic AI phrasing.
**Authority order (unchanged):** TOR → approved decisions → knowledge snapshot →
blueprint/constraints → historical style guidance (lowest). Exemplars can never
override the first four.

### Anti-copy enforcement
`validate_section.py` rejects a section as `VERBATIM_COPY` if it is too similar to a
retrieved exemplar, and `HISTORICAL_LEAK` if an old project/client token appears.
Final QA repeats these checks (`HISTORICAL_COPY`). Learn style, never reproduce text.

---

## Constraints (Winning Proposal Library)

- Historical proposals are STYLE exemplars — NEVER a source of current facts.
- NEVER copy historical paragraphs, client/project names, staff, dates, or counts.
- Corpus stays local (gitignored); never commit or print corpus content.
- Exemplar guidance is lowest authority — TOR/decisions/knowledge/constraints always win.

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

### 1a. Submission checklist (classified)

Immediately after analysis, build the submission checklist so every required item is
tracked by its real identity and obligation:

```bash
python "<plugin_root>/scripts/submission_checklist.py" "<run_dir>"
```

Present three groups — **MANDATORY**, **SCORING / COMPETITIVE**, **OPTIONAL** — using
the real item labels (e.g. "Detailed budget", "Example of previous work", "CV annex").
QA uses the SAME classifier, so a missing mandatory item is later reported by name
(never a generic "[SUBMISSION] requirement missing"). A competitive/scoring gap is a
recommendation, not a blocker.

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

### Step 2 — Present one decision at a time (native option cards)

Present each genuine proposal decision using the **native interactive
question / selectable-option UI** (AskUserQuestion-style cards) — **one decision
at a time**, never a wall of long prose. The descriptors are built deterministically
from the TOR; you do not invent options.

Get the next card (includes `progress_label` like "Decision 2 of 6"):
```bash
python "<plugin_root>/scripts/decision_cards.py" next "<run_dir>" --language <en|ar>
```
Use `--language ar` when the user is speaking Arabic; otherwise `en`. (You can also
fetch all actionable cards at once with `decision_cards.py list <run_dir>` if you
prefer to pre-read them — but still show ONE card to the user at a time.)

If `card` is null: all decisions reviewed — go to Step 4 (summary).

Render the returned `card` as a native question:
- **Question** = `card.question` (short). If present, show `card.tor_context` as a
  single one-line helper under the question (this is INFORMATION, not an option).
- **Progress** = `card.progress_label` (e.g. "Decision 2 of 6") as a short indicator.
- **Options** = `card.options`, each as a selectable choice using its `label`.
  - Exactly one option may carry `recommended: true` — mark it **"Recommended"** but
    **NEVER auto-select it**. The user must actively choose.
  - When `card.supports_custom` is true, the "Other / custom" option lets the user
    type their own answer (it is still validated against TOR constraints).
- The header chip = `card.header`.

**Separate INFORMATION from QUESTIONS.** Fixed TOR requirements are NOT questions and
never appear as cards (the builder excludes them). If the user asks about a fixed value,
see "Fixed requirement protection".

**Fallback (native UI unavailable).** If you cannot render selectable cards, show
`card.fallback_numbered` — a VERY SHORT numbered list (question + options + "reply with
the number"). Do NOT fall back to long narrative paragraphs.

### Step 3 — Record the user's choice immediately

Map the **selected option's `action`** to a `decision_register.py` command and run it
right away, so each decision is persisted before moving to the next card.

- `action: "set"` → use the option's `value`:
  ```bash
  python "<plugin_root>/scripts/decision_register.py" set "<run_dir>" "<decision_id>" <value>
  ```
  Numeric values are passed bare; text values are quoted (JSON-parsed).
  If exit code 4 (validation failure): show the stderr message and re-present the card.
  On success confirm briefly: `✓ Recorded: <value>`.

- `action: "custom"` (the "Other" option) → prompt the user for their exact value,
  then run the same `set` command. The register validates it against TOR bounds; on
  exit code 4, show the error and ask again. **Custom answers are still validated.**

- `action: "defer"` → ask for a brief reason, then:
  ```bash
  python "<plugin_root>/scripts/decision_register.py" defer "<run_dir>" "<decision_id>" "<reason>"
  ```

- `action: "unresolved"` → (optionally ask for a note, then):
  ```bash
  python "<plugin_root>/scripts/decision_register.py" unresolved "<run_dir>" "<decision_id>" "<notes>"
  ```

- `action: "recommend"` (the "Show me a recommendation" option) — two steps, never
  auto-approved:
  1. Analyze the TOR context, choose a value, and store it as a NON-authoritative
     recommendation:
     ```bash
     python "<plugin_root>/scripts/decision_register.py" recommend "<run_dir>" "<decision_id>" "<value>"
     ```
  2. Re-present the SAME card with the recommended value shown. The user must still
     actively approve it:
     ```bash
     python "<plugin_root>/scripts/decision_register.py" approve "<run_dir>" "<decision_id>"
     ```
  Only after `approve` is the decision RESOLVED.

**NEVER auto-select the recommended option and NEVER auto-approve a recommendation.**
The "Recommended" marker is guidance only; resolution always requires an explicit user
selection.

A `skip` command remains available if the user explicitly asks to skip a decision:
```bash
python "<plugin_root>/scripts/decision_register.py" skip "<run_dir>" "<decision_id>"
```

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

When the user is speaking Arabic, call `decision_cards.py` with `--language ar`. The
card's `question`, `tor_context`, and option **labels** come back in Arabic
(موصى به = Recommended, أخرى = Other, تأجيل = Defer, …), while the **canonical value
stored** in the register is unchanged (e.g. `30`, `INCLUDE`, `DEFER_TO_INCEPTION`).
The user reads Arabic; the register stays canonical.

Source text is always displayed as-is (preserved UTF-8). Constraint bounds and stored
values remain consistent regardless of display language.

Example Arabic card (rendered natively, one at a time):

```
القرار 2 من 6

ما العدد الذي تريد أرفادة اقتراحه للمقابلات؟
الـTOR: يجب إجراء ما لا يقل عن 30 مقابلة KII

◦ 30 — موصى به
◦ إدخال قيمة محددة
```

---

## Constraints (Decision Review)

- Present decisions as native selectable-option cards, ONE at a time, with a short
  progress indicator — never long narrative questions.
- Options come only from `decision_cards.py` (TOR constraints / valid semantics) —
  NEVER invent options.
- Exactly one option may be marked "Recommended"; NEVER auto-select or auto-approve it.
- Custom ("Other") answers are still validated against TOR constraints.
- NEVER auto-resolve a decision without explicit user confirmation.
- NEVER modify TOR-fixed requirements (they don't appear in the decision register).
- NEVER invent TOR constraints not in decision_candidates.json.
- If the run directory changes (different TOR), start a new analysis — do not apply decisions cross-TOR.
- Output directories (arfada-output/) are local only.

---

## 2a. Relevant experience selection

Rank ARFADA's past assignments for THIS TOR and let the user pick the final 3–5:

```bash
python "<plugin_root>/scripts/relevant_experience.py" "<run_dir>"
```

- Ranking uses country, assignment/evaluation type, sector(s), client/donor, and
  thematic similarity. The **current TOR/project is excluded** from retrieval so the
  proposal never cites itself.
- Present the `selection_card` options; the user selects 3–5 (never auto-select).
- `global_total_projects` in the output is ARFADA's **verified full-tracker** count —
  the run-scoped exclusion does NOT reduce it. Use `global_total_projects` for any
  "ARFADA has delivered N projects" statement, and the selected assignments for the
  featured examples.

---

## 2b. Evidence-first team facts

No named-person claim may enter the proposal without structured staff evidence.

- Prefer `query_knowledge.py search --type staff …` (normalized CV profiles with
  provenance). Numeric experience is parsed defensively — ages, project durations,
  date ranges, and beneficiary counts can never become "years of experience".
- If you read a CV directly and accept a fact, **promote it first** to a structured
  staff fact with provenance (`engine.tor.gknowledge.normalize.promote_staff_fact`)
  before using it. If evidence is unavailable, **omit or soften** the claim — never
  invent. Final QA flags unsupported named-person claims.

---

## 2c. Interactive budget builder

Use the **approved total budget** and **approved LOE**. Ask the user for each line
input (never invent a value):

- expert daily rates · field supervisor · enumerators · transport ·
  participant reimbursement · translation/transcription · editing/printing ·
  taxes/mandatory costs · other TOR-specific costs.

Preview the computed budget and show the reconciliation BEFORE approval:

```bash
# preview (shows reconciliation vs approved total)
echo '<budget_spec.json>' | python "<plugin_root>/scripts/budget_builder.py" "<run_dir>" --spec -
# approve (saves budget.json; refuses unless it reconciles exactly)
python "<plugin_root>/scripts/budget_builder.py" "<run_dir>" --spec spec.json --approve
```

Each line is computed automatically (quantity×rate, or a % of subtotal for taxes).
The detailed budget must reconcile EXACTLY to the approved total; Final QA blocks on a
reconciliation error or a missing input. Use the approved breakdown consistently in
the proposal's financial narrative.

---

## 2d. Previous-work annex

When the TOR requests an example of previous work:

```bash
python "<plugin_root>/scripts/previous_work.py" validate "<file>"
python "<plugin_root>/scripts/previous_work.py" register "<run_dir>" "<file>" [--confirm-clearance]
```

- The file must validate as an actual deliverable (evaluation / endline / final
  evaluation / assessment report) produced by/for ARFADA — **not** a proposal, TOR,
  policy, or branding/manual document.
- If ARFADA authorship/sharing clearance is not evident in the file, `register`
  requires `--confirm-clearance` (the user confirming ARFADA may share it).
- Registration copies the file into `annexes/previous_work/` and writes
  `previous_work.json`. **Never state that an example is annexed until the actual file
  exists in the run package.**

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
Hides all internal IDs, fact_ids, and system notes. **The client draft never contains
`[To be provided: ...]`** — an unresolved evidence gap is represented through the
decision/blocker system and the "DRAFT — HUMAN REVIEW REQUIRED" banner, not leaked
into the document (v0.6.4 §8). If a section has a hard unsupported-fact error,
**client export fails** (exit 5) — fix the section first. The internal footer uses the
**actual** plugin version and knowledge-snapshot version (never hard-coded).

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

---

## 6. Final Quality Review

Deterministic acceptance over all run artifacts. Produces a **GREEN / YELLOW / RED**
verdict. No model call. **GREEN means "automated QA passed — ready for final HUMAN
review", NOT "send blind".**

### Run it
```bash
python "<plugin_root>/scripts/final_qa.py" "<run_dir>"
```
Writes `final_qa.json` + `final_qa.md`. Exit code: 0 GREEN / 10 YELLOW / 20 RED.

Present the concise summary:
```
FINAL QUALITY REVIEW — <GREEN|YELLOW|RED>

Mandatory requirements: X/Y addressed
Critical failures: C   Errors: E   Warnings: W
Decisions respected: R/T

<list critical failures, then top warnings>

Recommendation:
  GREEN  → Ready for final human review.
  YELLOW → Review warnings, then export with confirmation.
  RED    → Fix critical issues before any client deliverable.
```

### What it checks
Requirement coverage (verified against actual content, not just the ledger),
ownership (orphans/duplicates/client-as-bidder), fixed TOR constraints, approved
decision compliance (and fabricated-decision detection), ARFADA fact support,
numeric contradictions across sections, assignment-type terminology, section
completeness, framework matrix, deliverables, workplan, team, submission, readability,
duplication, and **client-DOCX leakage** (internal IDs / local paths → CRITICAL).

**v0.6.4 additions:** missing mandatory submission items **by name** (e.g. "Detailed
budget missing") separated from scoring/competitive recommendations; claimed annexes
whose files do not exist (CV annex / previous-work / budget); budget reconciliation
errors + LOE mismatch; current-project contamination in past experience; client
placeholders (`[To be provided: ...]` / TBD); sampling-unit mismatch + sample
arithmetic; and expanded internal leakage (Master Tracker / knowledge-snapshot /
knowledge-folder references).

### Verdict rules
- **RED** — a mandatory requirement or **mandatory submission item** missing, a
  fixed-TOR contradiction, a fabricated decision, an unsupported critical fact, wrong
  client/country, a missing mandatory deliverable/framework, a **budget that does not
  reconcile**, a **claimed annex with no file**, a **client placeholder/internal
  leak**, a hard generation failure, or client-DOCX internal leakage.
- **YELLOW** — no critical failures but material errors/warnings or human-review items,
  including **scoring/competitive** gaps (a competitive improvement never forces RED
  unless the TOR makes it mandatory).
- **GREEN** — mandatory coverage adequate, no critical failures, facts/decisions/
  constraints/budget valid.

### Drill-down
On request: `show critical issues`, `show warnings`, `show missing requirements`,
`show requirement <id>`, `show decision compliance`, `show fact traceability`,
`show contradictions`, `show QA by section` — read `final_qa.json` and filter.

### Repair (bounded)
```bash
python "<plugin_root>/scripts/final_qa.py" "<run_dir>" --repair-plan
```
Gives a per-section repair plan. Regenerate ONLY the listed sections (max 2 cycles
each), re-validate them, then re-run Final QA. **NEVER** change an approved human
decision (sample count, staff, methodology choice, deferral, assignment type) to make
QA pass — human decisions are authoritative.

### Submission package check (before/after GREEN)
Verify the ACTUAL files exist — a textual "CVs annexed" is not proof:
```bash
python "<plugin_root>/scripts/submission_package.py" "<run_dir>"
```
Shows `proposal_final.docx`, required CVs, previous-work example, financial offer /
detailed budget, and any other TOR-required annex, with the real filenames present and
a list of what is still missing. Expectations come from the submission checklist.

### Export Final (gated + sanitized)
```bash
python "<plugin_root>/scripts/export_final.py" "<run_dir>"            # GREEN only
python "<plugin_root>/scripts/export_final.py" "<run_dir>" --confirm  # YELLOW w/ confirmation
```
- **GREEN** → produces `proposal_final.docx` and **removes the DRAFT / HUMAN-REVIEW
  stamp** (validated client content, no new content).
- **Confirmed YELLOW** → produces the final but **retains the DRAFT stamp**.
- **RED** → blocked (exit 20); no client deliverable. The internal review DOCX stays available.
- **All exports are sanitized**: `[To be provided: ...]` is stripped and the final is
  rejected if any internal marker or Knowledge/Master-Tracker/internal-review leakage
  remains — on failure it exits `FINAL_SANITIZE_FAILED` (30) and **deletes the final**.
`export_final.py` re-runs QA first, so a stale GREEN never slips through.

### Invalidation
A GREEN applies only to the exact reviewed artifacts (QA `fingerprint`). If the
proposal, Decision Register, or Knowledge Snapshot changes, re-run Final QA — do not
reuse a stale GREEN.

---

## Constraints (Final QA)

- Final QA is deterministic — no API, no network, no new content.
- GREEN ≠ "skip human review." Always recommend a final human read before submission.
- RED blocks the client deliverable; YELLOW needs confirmation; only GREEN is clean.
- Never auto-repair an approved human decision to force a pass.
