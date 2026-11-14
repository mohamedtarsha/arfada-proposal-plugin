# Changelog

All notable changes to `arfada-proposal` plugin are documented here.

Format: [Semantic Versioning](https://semver.org) — MAJOR.MINOR.PATCH

---

## [0.6.4] — 2026-11-14

### Production hardening — reusable workflow from the first real end-to-end run

No new development phase and no engine redesign: this pass productionizes the lessons
from the first completed ARFADA proposal so the next TOR needs far less manual work.

- **§1 Run initialization** — `run_init.py` reports, in one compact summary, the
  Knowledge source, Master Tracker, Staff CVs, Company docs, Previous Work library,
  Writing DNA, historical TOR↔Proposal pairs, plugin version, and knowledge-snapshot
  version. Writing DNA + exemplars persist across sessions and are auto-discovered; no
  re-index.
- **§2 Submission checklist** — `submission.py` + `submission_checklist.py` classify
  each submission requirement as MANDATORY / SCORING / OPTIONAL with a stable item
  identity. QA now reports a missing item by name ("Detailed budget missing"), never a
  generic "[SUBMISSION]".
- **§4 Evidence-first team facts** — hardened CV years-of-experience parsing (ages,
  project durations, date ranges, beneficiary counts can no longer become "years of
  experience"); new `promote_staff_fact()` turns a CV-read fact into a provenance-
  bearing staff fact before use.
- **§5 Relevant experience** — `relevant_projects()` now scores on country, type,
  sector(s), client/donor, evaluation type, and thematic similarity, and excludes the
  current TOR/project (run-scoped). The exclusion does NOT change the global portfolio
  count (verified full-tracker metric). `relevant_experience.py` emits selection cards.
- **§6 Previous-work annex** — `annex.py` + `previous_work.py` validate that a file is
  an actual evaluation/assessment deliverable by/for ARFADA (not a proposal/TOR/policy/
  branding), require clearance confirmation when authorship isn't evident, and register
  it into the run package. Nothing is "annexed" until the file exists.
- **§7 Interactive budget** — `budget.py` + `budget_builder.py` build a detailed budget
  from approved total + LOE and user-supplied line inputs (never invented), reconcile
  EXACTLY to the approved total, and show the reconciliation before approval.
- **§8 Client/internal separation** — the client draft no longer emits
  `[To be provided: ...]`; unresolved evidence is represented through the decision/
  blocker system + DRAFT banner.
- **§9 QA hardening** — new Final-QA checks: missing mandatory submission items by
  name, claimed annexes without files, budget reconciliation + LOE, current-project
  contamination in past experience, client placeholders, sampling-unit mismatch +
  sample arithmetic, expanded internal leakage. Mandatory compliance failures (RED) are
  separated from competitive recommendations (YELLOW at most).
- **§10 Final export** — `export_final.py` sanitizes the final: GREEN drops the DRAFT
  stamp, confirmed YELLOW retains it, RED blocks; strips `[To be provided: ...]`; and
  fails `FINAL_SANITIZE_FAILED` (deleting the final) if any internal/knowledge-tracker
  leakage remains.
- **§11 Submission package check** — `package.py` + `submission_package.py` verify the
  physical files (proposal_final.docx, CVs, previous-work example, budget, other
  annexes) exist — a textual "CVs annexed" is not accepted as proof.
- **§12 Runtime metadata** — `version.py` is the single source of truth; plugin and
  knowledge-snapshot versions are read at runtime (no hard-coded "0.5.0"/"0.6.0").

### §13 Regression
`tests/test_jordan_regression.py` models the completed Jordan child-labour run as a
regression fixture for the generalized workflow: GREEN QA with every mandatory
requirement addressed, no unsupported claims, no current-project contamination, exact
budget reconciliation, validated previous-work annex, client draft free of internal
markers, clean final export — plus guard-flip tests (non-reconciling budget → RED).

### Tests: +37 new (production hardening + Jordan regression). No approved content changed.

---

## [0.6.3] — 2026-11-10

### Changed — Decision Review UX: native interactive option cards (UX patch only)

Proposal Decision Review now uses Claude Code's **native interactive
question / selectable-option UI** (AskUserQuestion-style cards) instead of long
narrative questions. **No engine change:** decision semantics, TOR extraction,
generation, Writing DNA, and Final QA are untouched; decisions still persist through
the same `decision_register.py` with the same validation.

- New `engine/tor/decision_ui.py` — deterministic descriptor builder. Each genuine
  human decision becomes an option card: short question, optional one-line TOR context
  (INFORMATION separated from the QUESTION), and options drawn **only** from TOR
  constraints / valid semantics (never invented). Exactly one option may be marked
  **"Recommended"**, but it is **never auto-selected or auto-approved**. Shapes:
  ENUM → allowed options + "Other"; small RANGE → each value (midpoint recommended) +
  "Other"; wide RANGE → recommended midpoint + "Enter exact"; AT_LEAST → minimum
  (recommended) + "Enter exact"; DEFERRED → "Determine during inception" (recommended)
  / set now / show recommendation / leave unresolved; OPTIONAL_CHOICE → include /
  do-not-include / defer / unresolved. **FIXED requirements never become cards.**
  Numeric bounds and units carried through; custom ("Other") answers are still
  validated. Arabic labels (موصى به / أخرى / تأجيل …) with **canonical values stored
  internally**. Each card also carries a VERY SHORT numbered `fallback_numbered` for
  when the native UI is unavailable. Optional one-concise-card `expired_date_descriptor`
  for TORs whose dates are already past.
- New `scripts/decision_cards.py` — `list` / `next` emit ordered descriptors from the
  live register (merged with candidate `allowed_options`) with a progress indicator
  ("Decision 2 of 6"). Presentation only — it never writes decisions.
- SKILL "Review Proposal Decisions" rewritten: one card at a time, record immediately,
  recommendation routes `recommend → approve` (never auto-approve), Arabic via
  `--language ar`, short numbered fallback. Summary step unchanged.

### Tests: +33 (24 descriptor, 9 Jordan-endline card-flow regression). No generation run.

---

## [0.6.2] — 2026-11-10

### Fixed — Winning Proposal Library pairing (bugfix only; no new features)

A corpus-pairing diagnostic on the real library found 8/14 project folders unpaired
despite each containing a TOR + proposal. Two generic root causes, both fixed:

1. **Word-boundary bug:** filename TOR tokens glued to `_`/`-` (e.g. `ToR_NRC`,
   `BHA_TOR_Endline`, `RFQ_Section`, `Annex-1-ToRs`, `TOR_-_SRRVCM`, `TOR_SCI`,
   `ToR_OXFAM`, `ToR_Telethon`) were missed because `\btor\b` finds no boundary
   before `_` (an underscore is a word char). Replaced `\b…\b` with letters-only
   lookarounds `(?<![a-z])…(?![a-z])` so `_`/digits/hyphens count as boundaries
   (still rejects `tortoise`/`contractor`). Added tender / scope-of-work /
   schedule-of-requirements / annex+TOR cues.
2. **Cover-letter mis-pick:** a `..._Cover Letter.docx` matched proposal candidates
   (contains "ARFADA") and outranked the real `..._Proposal.docx`. Added deterministic
   proposal scoring: boost `proposal`/`technical`/`final`/`submitted`, demote
   `cover letter`/`draft`/`old`/`comment`/`backup`/`annex`.

Also (spec §6): **text-extractable PDF proposals now produce section exemplars**
(`_pdf_sections` via pypdf, no OCR) instead of metadata-only; genuinely scanned/
image-only PDFs stay metadata-only with a warning.

### Real-corpus result (local, not committed)
Project folders 14 · **Valid pairs 14** (was 6) · Ambiguous 0 · Unpaired 0 · Unreadable 0.
Writing DNA recomputed from 14 docs: ~33-word median paragraphs, ~13.4 tables/doc,
organizational voice; assignment types now include MIDLINE.

### Tests: 280/280 (6 new pairing regressions). No generation/QA/authority changes.

---

## [0.6.1] — 2026-11-10

### Added — Winning Proposal Library / ARFADA Writing DNA (style only, post-launch)

A local folder of past winning proposals teaches ARFADA's human writing style,
structure, formatting, and TOR→response patterns. **STYLE exemplars only — never a
factual source.** Strict separation: facts (Master Tracker/CVs/company/TOR/decisions)
stay authoritative; historical proposals are lowest-authority style guidance and are
never copied verbatim.

**New package `engine/tor/exemplars/`:**
- `exemplar_config.py` — library root get/set/clear (user config; `ARFADA_EXEMPLAR_ROOT` override)
- `scan.py` — recursive discovery, TOR↔proposal pairing (ambiguous excluded), section
  extraction, incremental (path+mtime) + transactional; cache under
  `~/.arfada-proposal/exemplars/` (gitignored); no OCR, scanned docs warn; prefers DOCX
- `dna.py` — Writing DNA (paragraph/sentence length, modal usage, voice, bullet/table
  frequency), Formatting DNA (section order), TOR→response patterns (rationale /
  respondents / triangulation / analysis / QA / ethics)
- `retrieval.py` — section-specific ranked retrieval (assignment type + country + region),
  top-3, bounded excerpts
- `anticopy.py` — deterministic similarity guard (8-gram overlap + longest shared run) +
  historical entity-leak detection

**New scripts:** `exemplar_library.py` (set/show/clear), `refresh_exemplars.py` (scan + --status).

**Wiring:** generation packets gain `style_guidance.writing_dna`,
`style_guidance.response_patterns`, and `historical_exemplars` at **LOWEST authority**
(TOR → decisions → knowledge snapshot → constraints → style). `validate_section.py`
rejects `VERBATIM_COPY` / `HISTORICAL_LEAK`; Final QA adds a `HISTORICAL_COPY` check.
Exemplars never populate `verified_arfada_facts` (source separation enforced structurally).

### Validated
- Real library (`Firass's Proposals`, local, not committed): 7 countries, 14 projects,
  6 valid pairs, 0 ambiguous/unreadable, 13 docs → Writing DNA (35-word median paragraphs,
  ~13 tables/doc, organizational voice). Section-specific retrieval returns distinct
  exemplars per section ranked by type+country. A/B: DNA-guided packet carries style
  guidance + bounded exemplars while `verified_arfada_facts` stays empty.
- Anti-copy: verbatim copy flagged, fresh/generic text clean, entity leak detected.

### Tests: 274/274 (20 new, synthetic fixtures only). Final QA still green. No corpus committed.

---

## [0.6.0] — 2026-11-10

### Added — Final Quality Review (PE7 lineage) — last core development phase

Deterministic proposal acceptance over the existing run artifacts. No model call,
no network, no new content. Returns **GREEN / YELLOW / RED**. GREEN = "automated QA
passed — ready for final HUMAN review", never "send blind".

**New: `engine/tor/final_qa.py`** — `Finding` model (stable id, severity, blocks_client)
+ `run_final_qa()` running 19 check families:
- artifact consistency (cross-run → CRITICAL), requirement coverage (verified against
  actual generated content, not just the ledger), ledger-substantive (false-coverage
  detection), ownership (orphan/duplicate/client-as-bidder), fixed TOR constraints,
  decision compliance (approved value present; below-minimum conflict → CRITICAL;
  fabricated unresolved decision → CRITICAL), personnel (unapproved named staff),
  ARFADA fact support (unsupported org number → ERROR), numeric contradictions across
  sections, assignment-type terminology, section completeness, framework matrix
  (missing → CRITICAL), deliverables (missing mandatory → CRITICAL), workplan, team,
  submission, readability (long paragraphs), duplication, and client-DOCX leakage
  (internal IDs / local paths → CRITICAL).
- GREEN/YELLOW/RED rollup; QA `fingerprint` (TOR identity + decision rev + snapshot id +
  section hashes + plugin version) so a GREEN applies only to the exact reviewed
  artifacts; `build_repair_plan()` (per-section, max 2 cycles, never touches decisions);
  Markdown report.

**New scripts:**
- `final_qa.py <run_dir> [--repair-plan]` — writes final_qa.json + final_qa.md; exit 0/10/20
- `export_final.py <run_dir> [--confirm]` — gated `proposal_final.docx`: GREEN exports,
  YELLOW needs --confirm, RED blocked (exit 20). Re-runs QA first (no stale GREEN).
  Final = validated client content; no new content introduced.

**SKILL.md v0.6.0:** Final Quality Review workflow (summary, drill-down, bounded repair,
gated export, invalidation). Menu now 6 actions.

### Validated (synthetic cases)
- A compliant proposal → **GREEN** (24/24 mandatory) → export allowed
- below-minimum KII count → **RED** → export blocked (exit 20)
- long paragraph only → **YELLOW** → export needs --confirm (exit 10 → 0 + proposal_final.docx)
- missing mandatory section → RED; fabricated unresolved decision → RED; cross-run → RED;
  unsupported ARFADA number → finding; numeric contradiction → finding; unapproved named
  staff → finding; fingerprint changes on section/decision edit

### Tests: 254/254 (19 new Final QA tests). No Anthropic API, no VPS, no MCP.

### End of core development — plugin is READY FOR TEAM USE.

---

## [0.5.2] — 2026-11-10

### Added — Phase 4.2 Local / synced knowledge folder (OAuth-free, PRIMARY source)

A single configurable **local folder** is now the primary ARFADA knowledge source.
It may be a plain folder or a **Google Drive for Desktop / OneDrive / Dropbox /
network-mounted** folder — the plugin only sees a filesystem path and calls **no
cloud API**. No OAuth, no VPS, no MCP, no Anthropic API.

**New package `engine/tor/lknowledge/`:**
- `local_config.py` — `knowledge_root` get/set/clear (user config dir; `ARFADA_KNOWLEDGE_ROOT` override)
- `scan.py` — deterministic folder scan → normalized cache:
  - `Projects/Master Tracker.xlsx` via openpyxl → project records + metrics (Python sums)
  - `Staff CVs/<Country>/` recursive PDF/DOCX → profiles (country from subfolder; scanned → LOW confidence)
  - `Company/` document index; `Brand/` logo detection
  - incremental (path + modifiedTime), transactional (failed scan keeps prior cache)
  - cloud-placeholder detection → `FILE_NOT_AVAILABLE_LOCALLY` (0-byte / offline attr), skipped safely

**Source priority (spec §3):** frozen snapshot > **LOCAL_FOLDER** > GOOGLE_API (optional) > STATIC_FALLBACK.
Cache `source_mode` records origin; `knowledge.py`, `snapshot.py`, `knowledge_status.py` honor it.
Google OAuth connector retained but **OPTIONAL/ADVANCED** — not required for setup or routine use.

**New scripts:** `knowledge_folder.py` (set/show/clear), `refresh_knowledge.py` (local-first,
Google fallback). `knowledge_status.py` now shows LOCAL_FOLDER + knowledge root.

**Wiring:** `build_blueprint.py` freezes a `source_mode=LOCAL_FOLDER` snapshot (Master
Tracker file hash + modified time in the manifest); `render_docx.py` embeds the local
brand logo; local filesystem paths never leak into client DOCX.

### Validated (synthetic ARFADA Knowledge folder, no real data)
- set folder → refresh → status: LOCAL_FOLDER, 3 projects, 2000 surveys / 65 KII, 2 CVs, logo found
- xlsx parsing, recursive CV discovery, empty-cell→None, file-hash provenance
- incremental unchanged/added/removed; transactional bad-root keeps prior cache
- cloud-placeholder (0-byte) reported unavailable, real CVs still indexed
- LOCAL_FOLDER snapshot immutable on local file change; manifest revision present
- end-to-end: local folder → snapshot → generate (live 2000-survey claim accepted) →
  internal DOCX with embedded local logo; client DOCX leaks no local paths
- Google is optional (works with Google never configured)

### Tests: 235/235 (23 new Phase 4.2 local-folder tests). No OAuth, no API, no VPS, no MCP.

---

## [0.5.1] — 2026-11-10

### Added — Phase 4.1 Live Google Workspace Knowledge Connector (local-only)

Google Drive/Sheets become the LIVE operational source of truth; the static
`knowledge/` snapshot remains an explicit **STATIC_FALLBACK**. Everything runs
locally — no VPS, no MCP server, no Anthropic API. Google is the only external
data connection (read-only).

**New package `engine/tor/gknowledge/`:**
- `paths.py` — user-local dirs (`~/.arfada-proposal/`, `ARFADA_HOME` override); tokens/cache NEVER in repo
- `auth.py` — OAuth desktop flow (read-only Drive+Sheets scopes); tokens stored locally, never printed
- `config.py` — `arfada_sources.yaml` loader (source IDs only, never credentials)
- `clients.py` — Drive/Sheets clients behind an injectable protocol (tests use fakes)
- `normalize.py` — Master Tracker rows → project records (empty cells → None, never invented) +
  deterministic metric aggregation (Python sums, never the model); CV text → staff profiles with evidence
- `cache.py` — local normalized cache; atomic writes; freshness/age
- `sync.py` — incremental (by modifiedTime), transactional (failed sync keeps prior cache);
  added/updated/unchanged/removed report; deleted-file handling
- `snapshot.py` — per-run frozen knowledge snapshot + manifest (snapshot_id, source_mode,
  revisions, sync times, plugin_version); **immutable** once created

**`engine/tor/knowledge.py`** — source priority: frozen run snapshot > live Google cache >
STATIC_FALLBACK. Live metrics/projects override static. New `search_staff()` (hard min-years
filter + soft ranking; candidates are NOT auto-approved).

**New scripts:** `connect_google.py`, `sync_google_knowledge.py`, `knowledge_status.py`.
**Config:** `config/arfada_sources.example.yaml` (IDs only). **.gitignore:** tokens, client
secrets, `.arfada-proposal/`, cache, real `arfada_sources.yaml`.

**Wiring:** `build_blueprint.py` freezes the snapshot at generation start; `prepare_section.py`
reads facts from the frozen snapshot (`Knowledge(run_dir)`); `render_docx.py` auto-resolves the
brand logo from the live cache (falls back to neutral cover).

### Behaviour
- Static metrics (146/2558/1556/69698) are NOT silently authoritative once live Google is active;
  live normalized source takes priority (reconciliation is explicit, not automatic overwrite).
- Numeric org claims must trace to a snapshot metric fact; else NEEDS_ARFADA_EVIDENCE.
- Offline: a valid cache is usable (LIVE_GOOGLE_OFFLINE_CACHE); never-connected → STATIC_FALLBACK.

### Validated (mocked Google, no credentials)
- sheet→3 normalized projects; metrics 2000 surveys / 65 KII / 10 FGD (deterministic)
- incremental unchanged/added/removed; transactional failure keeps prior cache
- snapshot immutability (live change does not mutate a frozen run); cross-run isolation
- live overrides static; static fallback labeled; staff min-years filter + ranking
- numeric claim traces to snapshot fact

### Not run here (requires user's machine)
- Real OAuth consent + real ARFADA Google sources: must be run by the user with
  `connect_google.py` + authorized `client_secret.json` + `arfada_sources.yaml`
  (browser + credentials unavailable in this build env). Static-vs-live comparison
  and CV-folder validation run against real data once connected.

### Tests: 212/212 (31 new Phase 4.1, mocked Google). No Anthropic API, no VPS, no MCP.

---

## [0.5.0] — 2026-11-10

### Added — Phase 4 Verified Knowledge + Assignment Type + Professional DOCX

**Assignment-type inference (`engine/tor/assignment_type.py`)**
- Deterministic content-based inference (title/objectives/scope/requirements)
- 13-type taxonomy: EVALUATION / BASELINE / MIDLINE / ENDLINE / NEEDS_ASSESSMENT /
  TPM / MONITORING / RESEARCH_STUDY / SURVEY / ASSESSMENT / CAPACITY_ASSESSMENT /
  MARKET_ASSESSMENT / OTHER
- Presence-weighted scoring with capped frequency bonus (specific signals beat
  repeated generic words); confidence HIGH/MEDIUM/LOW + evidence snippets
- **No fixed "evaluation" default**: LOW confidence surfaces a `dec_assignment_type`
  classification decision; persisted in tor_analysis.json

**Type-specific blueprint (`engine/tor/blueprint.py`)**
- Framework section is now type-driven: Evaluation Framework / Assessment Framework /
  Monitoring Framework / Research Framework — distinct key, title, purpose, AND
  matrix columns (not a heading rename). Requirement ownership stays authoritative.

**Verified ARFADA Knowledge layer**
- `knowledge/` snapshot: arfada_profile.json, arfada_metrics.json, arfada_projects.json,
  provenance.json, KNOWLEDGE_VERSION (versioned in Git; refresh → bump → push)
- `engine/tor/knowledge.py`: fact lookup, numeric authority (totals are deterministic
  lookups, never recomputed), relevant-experience matching (metadata only, no prose)
- `scripts/query_knowledge.py`: version | metrics | fact | metric | search
- Facts injected into generation packets as `verified_arfada_facts` (each with
  fact_id + source + knowledge_version)

**Fact-claim validation (`engine/tor/generation.py`)**
- An ARFADA organizational/numeric claim is allowed ONLY if it matches a verified
  fact value, OR carries a NEEDS_ARFADA_EVIDENCE placeholder; otherwise
  `UNSUPPORTED_ARFADA_CLAIM` (hard error). TEAM: no invented names.

**Professional DOCX export (`engine/tor/docx_render.py` + `scripts/render_docx.py`)**
- python-docx only (no MS Word automation, no LibreOffice); cross-platform
- Named ARFADA style system, cover page, real headings, bullet/numbered lists,
  real Word tables (never tab-faked)
- Two variants: `--internal` (shows gaps + provenance + version footer) and
  `--client` (hides all internal IDs/fact_ids/notes; "DRAFT — HUMAN REVIEW REQUIRED"
  banner when gaps remain)
- Optional `--logo` (never fabricated; see assets/brand/README.md)

**Pre-export QA (`engine/tor/preexport_qa.py`)**
- Re-validates sections, checks decision values, unsupported facts, cross-TOR,
  client-leakage. Hard unsupported-fact error **blocks client export** (exit 5).

**Versioning:** every proposal records plugin_version + knowledge_version + run_id.

### Validated (live, local)
- NRC (type resolved → EVALUATION): 12-section blueprint, Evaluation Framework
- SRRVCM market TOR (→ MARKET_ASSESSMENT): builds **Market Assessment Framework**,
  NOT an evaluation shape — confirms no evaluation default
- Verified fact (2,558 KIIs) accepted; fabricated "200 evaluations" rejected
- Internal + client DOCX render with real 4×4 table; client hides internal markers;
  client export blocked by an unsupported-fact error
- 10-fact traceability (fact_id → source → knowledge_version)

### Tests: 181/181 (36 new Phase 4 tests). No Anthropic API.

---

## [0.4.0] — 2026-11-10

### Added — Phase 3 Controlled Proposal Generation

**Architectural rule:** the active Claude Code session is the generator. NO separate
Anthropic API, NO ANTHROPIC_API_KEY, NO provider client. Python is deterministic
plumbing; the session writes content against bounded packets. (Two tests assert the
absence of any Anthropic/provider usage in engine + scripts.)

**New: `engine/tor/blueprint.py`** (deterministic, PE5-A lineage, plugin-native)
- Assignment-aware section set (16-section taxonomy, canonical ordering)
- Requirement ownership: each bidder requirement → exactly ONE owning section (no double-count)
- Response slots: one per bidder requirement, with response mode + minimum expectation
- Decision dependencies propagated from the Decision Register
- CLIENT requirements never produce slots; TEAM/EXPERIENCE flagged needs-evidence

**New: `engine/tor/generation.py`** (deterministic)
- `build_packet()` — bounded, section-scoped generation packet (only relevant context):
  purpose, owned requirements, mandatory slots, applied decisions (resolved values +
  deferrals), allowed facts, forbidden fact categories, output contract, writing guidance
- Block schema: paragraph | bullet_list | numbered_list | table | evidence_placeholder
- `validate_candidate()` — schema, duplicate/missing block_ids, table row width,
  ledger→block linkage, mandatory-slot coverage, **approved decision value enforced
  exactly** (writing 40 when 35 approved is a hard error), unsupported-ARFADA-fact
  detection (requires NEEDS_ARFADA_EVIDENCE placeholder)
- `build_repair_packet()` — narrow retry packet; max 2 repair attempts per section
- Generation status + resume (`next_pending_section`, EXECUTIVE_SUMMARY always last)
- Atomic JSON writes; `section_to_markdown()` renderer

**New CLI scripts:**
- `build_blueprint.py <run_dir>` — writes proposal_blueprint.json + generation_status.json
  (validates run identity; rejects cross-TOR registers with exit 3)
- `prepare_section.py <run_dir> <section_id>` — writes generation_packets/<section>.json
- `validate_section.py <run_dir> <section_id> <candidate.json>` — validates + persists
  generated_sections/<section>.{json,md}, or exit 4 + repair packet
- `generation_status.py <run_dir> [--next]` — resume state
- `assemble_draft.py <run_dir>` — proposal_draft.md + coverage report

**New artifacts:**
```
proposal_blueprint.json, generation_status.json,
generation_packets/<section>.json, generated_sections/<section>.{json,md},
proposal_draft.md
```

**SKILL.md v0.4.0:** full Generate Proposal Draft workflow — session reads packet,
writes structured candidate, validates, repairs (bounded), assembles. Partial
generation allowed (blocked sections skipped). Menu now: Analyze TOR | Review
Proposal Decisions | Generate Proposal Draft.

### Validated (live, local)
- NRC TOR (prescriptive, 0 decisions): 12-section blueprint, 66 requirements owned,
  0 blocked; real DELIVERABLES table generated + validated READY; draft assembled
- Synthetic TOR with decisions: KII resolved to 35, FGD to 7 → packet injects exact
  values; METHODOLOGY generated with 35/7 passes; writing 40 is REJECTED (hard error)
- Fixed-value protection, cross-TOR protection, resume, repair cap all verified

### Tests: 145/145 (31 new Phase 3 tests). No Anthropic API.

---

## [0.3.0] — 2026-11-07

### Added — Phase 2 Human Decision Review

**New: `engine/tor/register.py`**
- `DecisionRegister` + `DecisionEntry` dataclasses with stable JSON schema (v1)
- Status model: OPEN | RESOLVED | DEFERRED | SKIPPED | UNRESOLVED | RECOMMENDATION
- `init_register()` — builds register from decision_candidates.json (human decisions only)
- `set_decision()` — resolve with value, validated against TOR constraints
- `defer_decision()` / `skip_decision()` / `unresolve_decision()` / `clear_decision()`
- `set_recommendation()` / `approve_recommendation()` — Claude suggests, user approves
- `validate_value()` — rejects values below minimum / above maximum
- `get_summary()` / `next_open()` — resume support
- Atomic writes (temp-file → validate → rename); `tor_identity` guards cross-TOR apply

**New: `scripts/decision_register.py`** (CLI bridge)
- Commands: init | show | get | set | defer | skip | unresolved | clear |
  recommend | approve | next | summary
- UTF-8 buffered output (Arabic + special chars safe)
- Exit code 4 on constraint-validation failure

**New output artifact:** `decision_register.json` (alongside tor_analysis.json,
requirements.json, decision_candidates.json, analysis_summary.md)

**SKILL.md v0.3.0:** full conversational Decision Review workflow — one decision
at a time, constraint display, recommendation flow (never auto-resolve), resume,
edit/clear, Arabic UX.

### Behaviour
- Only genuine proposal decisions (OPEN_PROPOSAL_DECISION / DEFERRED_DECISION /
  OPTIONAL_CHOICE) enter the register; FIXED constraints never appear.
- Numeric choices validated: e.g. "at least 30 KIIs" rejects 25, accepts 35.
- Range choices validated: "6-8 FGDs" rejects 10, accepts 7.
- APPROX targets displayed as approximate (not open choice).
- Recommendations stored as RECOMMENDATION — only RESOLVED on explicit approval.
- Resumable: re-entering continues from next OPEN decision.

### Validated (live, local)
- synthetic_en.docx: 4 decisions — numeric validation + text + resume + edit + clear
- synthetic_ar.docx: 2 decisions — Arabic UTF-8 preserved in register
- OXFAM Lebanon PDF: 1 decision (APPROX correctly a constraint, not a decision)

### Tests: 114/114 (25 new Phase 2 tests)

---

## [0.2.2] — 2026-11-07

### Added — Phase 1.2 Decision Semantics Hardening

**New: `engine/tor/decision_model.py`**
- `DecisionCandidate` dataclass: decision_id, decision_type, is_human_decision (backward-compatible),
  question, constraint_type, minimum, maximum, reason, source_text, category, actor
- `classify_decision(req, actor)` → richer type replacing simple boolean
- Decision types: FIXED_REQUIREMENT | FIXED_MINIMUM | FIXED_MAXIMUM | FIXED_RANGE |
  OPEN_PROPOSAL_DECISION | DEFERRED_DECISION | OPTIONAL_CHOICE | NO_DECISION
- `validate_proposed_value(candidate, proposed)` — constraint enforcement
- Category-aware rules: TEAM/ELIGIBILITY minimums → FIXED_MINIMUM; SUBMISSION → FIXED_REQUIREMENT
- Method-count rule: AT_LEAST on method instances (KII, FGD, مقابلة) → bounded OPEN_PROPOSAL_DECISION
- APPROX in sampling/methodology → FIXED_MINIMUM (approximate target, not open choice)
- CLIENT actor → NO_DECISION always
- DEFERRED language → DEFERRED_DECISION

**Arabic quantity patterns in `value.py`:**
- Arabic AT_LEAST: على الأقل, لا يقل عن, ما لا يقل عن
- Arabic AT_MOST: لا يتجاوز, لا يزيد عن
- Arabic APPROX: حوالي, نحو, تقريباً
- Arabic trail units: مقابلة, مجموعات, مستجيب, etc.

**New artifact: `decision_candidates.json`**
- Validated candidates for Phase 2 Decision Review
- Separates constraints from proposal decisions
- Each candidate has bounded question + constraint bounds

**Summary now shows:**
- Proposal decisions requiring review (genuine choices)
- Deferred decisions (to inception phase)
- TOR constraints (fixed, no choice needed)

**Tests:** 23 new Phase 1.2 tests (89 total)

### Fixed
- Phase 1.1 false positives eliminated:
  - "10 سنوات على الأقل" (team leader): was DECISION → now FIXED_MINIMUM ✓
  - "على الأقل اثنين من المعددين" (enumerators): was DECISION → now FIXED_MINIMUM ✓
  - "حوالي 400 مستجيب" (approx sample): was DECISION → now FIXED_MINIMUM ✓
- Decision fallback constrained to explicit open-choice language only
  (APPROX/AT_LEAST quantity patterns no longer upgrade FIXED_MINIMUM to OPEN_PROPOSAL_DECISION)

### Arabic before/after (Phase 1.1 → 1.2)
| | 1.1 | 1.2 |
|---|---|---|
| Proposal decisions | 5 | **2** |
| False positives | 2 | **0** |
| Genuine decisions | 3 | **2** |
| Constraints | — | **12** |

---

## [0.2.1] — 2026-11-07

### Added — Phase 1.1 TOR Hardening

**Arabic extraction (engine/tor/extractor.py):**
- Arabic obligation cues: يجب، ينبغي، يتعين، يلتزم، يلزم، يشترط، يُطلب، مطلوب، لا بد من
- Arabic prohibition: يجب ألا، لا يجوز، يحظر، غير مسموح
- Arabic exclusion: غير مطلوب، لا يُطلب
- Arabic optional: يمكن، قد يكون
- Arabic background filter: يهدف / تم / جرى sentences correctly excluded
- Arabic client responsibilities: ستوفر الجهة / ستقوم الجهة extracted with actor=CLIENT
- Arabic heading aliases for all 14 field categories
- `_match_field_ar()` checked before English aliases

**Arabic actor/decision detection (scripts/analyze_tor.py):**
- Arabic BIDDER cues: على الاستشاري / على مقدم العرض / يلتزم الاستشاري
- Arabic CLIENT cues: ستوفر الجهة / ستقوم الجهة / سيوفر العميل
- Arabic open-choice: حسب ما يراه مناسباً / وفق المنهجية المقترحة
- Arabic approximate quantity: حوالي / نحو / على الأقل / لا يقل عن
- Arabic AT_MOST protection: لا يتجاوز / لا يزيد عن → NOT flagged as decisions
- Language detection heuristic (english / arabic / mixed)

**PDF table extraction (engine/tor/adapter.py):**
- pdfplumber-based structured table extraction (Phase 1.1)
- Locator format: p{page}:tbl{idx}:r{row}c{col}
- Graceful fallback to pypdf text-only when pdfplumber unavailable
- `_pdf_tables_unavailable` diagnostic flag

**Deliverable calibration (engine/tor/structuring.py):**
- Removed overly broad keywords (methodology, tools, bare workshop)
- Three-path qualification: EXPLICIT_CATEGORY | DELIVERABLE_SECTION | EXPLICIT_MODAL_OUTPUT
- `qualify_reason` field on every deliverable record
- NRC TOR: deliverables now 4 (matches PE2 exactly, was 13)

**Diagnostics in tor_analysis.json:**
- language_detected, total_blocks, heading/list/table_cell block counts
- pdf_tables_found, pdf_tables_unavailable, pdf_table_cells
- requirements_from_tables, deliverables_detected, open_decisions_detected

**Tests:** 29 new Phase 1.1 tests (66 total, all passing)

### Fixed
- NRC regression: 66/66 requirements maintained (deliverable count now exactly matches PE2)
- DOCX list items now correctly classified when "List Bullet" style (not just numPr)

### Known limitations
- Arabic optional sentences (يمكن) not always extracted (Phase 1.2 target)
- PDF tables: requirements_from_tables=0 for most PDFs (table content categorization pending)
- DOCX page numbers remain unavailable (structural provenance sufficient)

---

## [0.2.0] — 2026-11-07

### Added
- **TOR Analysis** — first real engine capability
  - `engine/tor/` package: PE2-compatible deterministic extraction (models, fields, value,
    extractor, structuring) migrated from `phase-pe2-tor-intelligence@857e56b`
  - `engine/tor/adapter.py` — FileStore: PDF + DOCX → PE2 block format (no SQLite, no server)
  - `scripts/analyze_tor.py` — CLI bridge: runs extraction, writes JSON + Markdown artifacts
    to `arfada-output/<run_id>/`
  - Human-decision detection: AT_LEAST / APPROX / RANGE quantities + open-choice language
  - Actor classification: BIDDER / CLIENT per requirement
  - First-class objects: deliverables, submission, team, timeline, eval questions, methodology
  - SKILL.md v0.2.0: full Analyze TOR workflow, drill-down instructions for Claude
  - 37-test suite on synthetic DOCX + PDF + Arabic UTF-8 fixtures
- No ANTHROPIC_API_KEY required — all extraction is deterministic Python;
  Claude Code's active session performs semantic presentation

### Validated
- NRC TOR (real corpus): 66 requirements, all mandatory, exact category match vs PE2 engine
- Arabic UTF-8 preserved in all JSON artifacts
- Paths with spaces: working on Windows

### Not yet included
- Arabic-language obligation extraction (English modal patterns only)
- Proposal generation (Phase 2)
- RAG search (Phase 2+)

---

## [0.1.2] — 2026-11-07

### Changed
- Greeting: "ARFADA Proposal Assistant v0.1.2 — GitHub update verified."
- Proves full GitHub push → `claude plugin marketplace update` → new version active.

---

## [0.1.1] — 2026-11-07

### Changed
- Greeting updated: "ARFADA Proposal Assistant v0.1.1 — ready for TOR analysis."
- Version bump proof: confirms GitHub distribution update flow works end-to-end.

---

## [0.1.0] — 2026-11-07

### Added
- Initial plugin shell (`Phase 0`)
- Plugin manifest: `.claude-plugin/plugin.json`
- First skill: `skills/arfada-proposal/SKILL.md`
  - Self-identification as ARFADA Proposal Assistant v0.1.0
  - Version and status reporting
  - TOR receipt and acknowledgement
  - Roadmap communication (Phase 1 engine integration)
- Repository structure for private GitHub distribution
- `.gitignore` with security rules (no keys, no TOR data, no proposals)

### Not yet included
- Proposal engine (PE1–PE7)
- RAG pipeline integration
- K3 intelligence router
- Cited paragraph generation
- Full TOR-to-proposal draft

---

## Planned

### [0.2.0] — Phase 1
- Connect ARFADA RAG pipeline
- `/arfada-proposal search <query>` subcommand

### [0.3.0] — Phase 2
- `/arfada-proposal write <section>` — cited paragraph generation

### [1.0.0] — Phase 3
- Full TOR analysis + proposal draft
- `/arfada-proposal draft` — complete pipeline
