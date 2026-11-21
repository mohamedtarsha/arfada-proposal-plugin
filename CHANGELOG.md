# Changelog

All notable changes to `arfada-proposal` plugin are documented here.

Format: [Semantic Versioning](https://semver.org) — MAJOR.MINOR.PATCH

---

## [0.6.12] — 2026-11-21

### Fixed — confirmed v0.6.11 South Darfur output
- **Previous-work selection ≠ sharing clearance** (`engine/tor/previous_work_state.py`).
  `previous_work.json` keeps PREVIOUS_WORK_SELECTED and PREVIOUS_WORK_CLEARANCE apart.
  `register` records the selection only; clearance needs explicit permission wording
  (`previous_work.py clear --note …`). ARFADA authorship, a bare `--confirm-clearance`
  or the legacy `clearance_confirmed` flag never clear a report. Until cleared,
  PREVIOUS_WORK_CLEARANCE is one canonical final blocker, and "accompanies this
  proposal", "as a separate annex", "attached", "enclosed" … are contradictions
  (rewritten to safe wording on export); naming the proposed report stays allowed.
- **Stable staff identity** (`lknowledge/staff_identity.py`): `staff_profile_id` is the
  identity everywhere (ranking, team, facts, packets, validation, rendering);
  `canonical_name` is the full name (VERIFIED from a promoted CV fact, else PROVISIONAL
  from a person-named folder or the cleaned file name). People match only on the full
  name in order or a shared person folder — never shared tokens (Ahmed / Mohamed /
  Ishag …). Initials forms are flagged (STAFF_IDENTITY) and rendered in full.
  `promote_staff_fact` accepts `staff_profile_id`.
- **Submission requirement vs physical annex** (`engine/tor/submission.py`): only CVs,
  previous work, budget, registration or an explicitly requested separate file are
  package files. No generic `Annex: other`; deadline / channel lines are status items;
  a content item (e.g. Risk Mitigation Plan) is satisfied inside the technical
  proposal, otherwise a draft-coverage warning — never a package blocker.
- **Numeric QA tokenization** (`engine/tor/numeric_tokens.py`): typed tokens
  (PERCENTAGE, YEAR, DURATION, IDENTIFIER, MONEY, PORTFOLIO_METRIC, HISTORICAL_STAT,
  METHODOLOGY_COUNT). "73,906" is one number, "CFGB 3350" an identifier, "30 days" a
  duration; only portfolio metrics are checked against verified ARFADA facts. Counts
  never split decimals ("247.5"). Sampling provenance (minimum → allowance → adjusted
  → proposed, rounding upward) is parsed and checked; the baseline sample stays
  separate. The TOR's duration wording is kept ("30 days" is not rewritten to
  "30 working days"; DURATION_WORDING finding + export rewrite).
- **Role-specific staff ranking** (`lknowledge/staff_role_fit.py`): `role_fit_score` per
  TOR role (Team Leader, FSL, Gender/Protection, Data Analyst, Field Coordinator) from
  evidence only — CV-text snippets of the TOR's own candidate pool (cached, never full
  CV text), ARFADA filing at half weight, role titles only for "held this role".
  One distinct person per role, Team Leader question on role fit; SUPPORTING_DOCUMENT
  stays ineligible. Without TOR team roles the ranking is unchanged.
- Regression tests: `tests/test_v0612_regression.py` (+ updated v0.6.9 clearance test).

---

## [0.6.11] — 2026-11-21

### Production hardening — no claim may contradict the evidence or package state
- **Claim state model** (`engine/tor/claim_state.py` → `claim_state.json`): VERIFIED /
  PROVISIONAL / UNVERIFIED / MISSING / NOT_APPLICABLE for registration evidence,
  financial proposal, previous-work sample, team CV package, team availability,
  submission channel (placeholder → MISSING), deadline (ambiguous / passed →
  PROVISIONAL), field roster and per-person attributes — built only from the run's
  own artifacts. `analyze_tor` keeps the TOR's submission-instruction sentences.
- **Generation claim gating**: packets carry `claim_state` + `claim_policy` (safe
  wording per unresolved fact); `validate_candidate` rejects definitive language for
  unresolved facts (`CLAIM_CONTRADICTION`) and unverified personnel qualifications
  (`UNVERIFIED_PERSONNEL_CLAIM`). Pre-export re-validation uses the live state.
- **Staff evidence gating** (`lknowledge/staff_evidence.py`): years, FSL, evaluation,
  country / local, safeguarding / gender / protection, tools and languages each get a
  status from CV evidence text (VERIFIED), ARFADA's filing folder (PROVISIONAL) or
  nothing (UNVERIFIED); a job title alone is never sector expertise. Nomination no
  longer credits theme / evaluation / geography from parsed job titles; team entries
  carry `evidence_claims`. **Field-roster readiness** needs usable field CVs in the
  target area (VERIFIED), not just a country folder.
- **TOR source-inconsistency register** (`engine/tor/source_consistency.py` →
  `source_inconsistencies.json`): percentages that do not reconcile, category counts
  above a stated total, overlapping ranges, mixed stage terminology. Logged as
  SOURCE_INCONSISTENCY (INFO), values never changed.
- **Canonical submission blockers** (`engine/tor/canonical_blockers.py`): one blocker per
  unresolved item (FINANCIAL_PROPOSAL, PREVIOUS_WORK_SAMPLE, REGISTRATION_EVIDENCE,
  TEAM_CV_PACKAGE, TEAM_AVAILABILITY, SUBMISSION_CHANNEL, DEADLINE_CONFIRMATION,
  OTHER:…); duplicates collapse with their sources kept; `proposal_final.docx` and the
  technical proposal itself are export steps, never substantive blockers.
- **Final-language sanitizer** (`engine/tor/claim_language.py`, used by `docx_render`):
  client-style outputs rewrite contradicting sentences to the safe wording; a claim
  with no deterministic rewrite blocks the client export (the working draft still
  renders and reports it).
- **Semantic consistency QA** (separate from numeric QA): CLAIM_CONSISTENCY,
  PERSONNEL_EVIDENCE, SEMANTIC_CONSISTENCY (Impact Evaluation vs contribution-only
  inference, roster claims without evidence), SOURCE_INCONSISTENCY.
- Draft v1/v2 still render with unresolved items (provisional wording); submission
  package stays NOT_READY until every canonical blocker is resolved.
- Regression tests: `tests/test_v0611_claim_gating.py` (generic + South Darfur + an
  unrelated Iraq WASH TOR; optional `ARFADA_REAL_TOR`).

---

## [0.6.10] — 2026-11-21

### Fixed — real-TOR regression (original South Darfur ZOA PDF failed on v0.6.9)
- **Layout-tolerant title** (`engine/tor/tor_metadata.py`). PDF extraction puts page-1
  table cells before the text and merges the heading with "Terms of Reference (ToR)
  Background …". Titles now come from first-page text blocks before table cells; a
  heading embedded at the start of a long block is cut at the first section marker
  (Terms of Reference / ToR / Background / Introduction / RFP / "1. …"). Table
  field/value pairs ("Indicator: Baseline", "Location: Sudan") and keyword-only
  candidates ("Baseline", "Final Evaluation") are never titles.
- **Assignment type robust to title failures** (`engine/tor/assignment_type.py`). A
  suspicious title (short "field: value" pair, or LOW confidence) is ignored. More
  references to an existing baseline are discounted (established baseline information,
  baseline assessment conducted, in/established in the baseline, baseline benchmarks,
  baseline survey methods / process, experience in conducting baseline surveys).
- **Numbered submission items** (`engine/tor/extractor.py`). Inside a list introduced by
  an explicit submission cue ("Interested parties must submit the following:",
  "The proposal must include …"), numbered HEADING blocks are submission
  requirements (lower-case continuation lines merged). Headings elsewhere are untouched.
- **Submission blockers** (`engine/tor/submission_blockers.py`). Required registration
  evidence ("Evidence of registration …") without a file under `annexes/registration/`
  is a FINAL_SUBMISSION_BLOCKER, alongside budget and previous work. Never a draft
  blocker. Checklist items without a known identity keep the TOR's own item name.
- **Coordinated localities**: "Nyala Shamal and Nyala Janoub localities" yields both
  names; places are reported in document order.
- Regression tests: `tests/test_v0610_real_pdf_pattern.py` with a PDF fixture that
  reproduces the real extraction pattern (`tests/fixtures/south_darfur_pdf.py`); set
  `ARFADA_REAL_TOR` to run the same checks on the original PDF (never committed).

---

## [0.6.9] — 2026-11-21

### Fixed — four issues from the fresh South Darfur v0.6.8 Fast Mode test
- **TOR metadata from the document** (`engine/tor/tor_metadata.py`). File-based TORs
  had no title, client or country. The title now comes from an explicit title label or
  the first-page assignment heading; the client from explicit commissioning wording
  ("ZOA is seeking …", "commissioned by …", "Client: …"; a donor is never the client);
  the country from the assignment location (location labels, the title, "in …,
  Sudan"); and `subnational_location` from the named states / localities. Values the
  text does not state stay empty. Team ranking and experience retrieval then use the
  extracted country and client; tracker rows coded EVALUATION whose name says
  endline / final evaluation now match an ENDLINE TOR.
- **Submission blockers** (`engine/tor/submission_blockers.py`). A TOR-required
  financial proposal / detailed budget without a reconciled budget, and a required
  previous-work example without a cleared, annexed file, are FINAL_SUBMISSION_BLOCKER
  items in the two-status report and `fast_proposal.py status` (also when the TOR lists
  them under "the proposal must include"). They never block the draft.
  "Examples of previous …" is now recognised as the previous-work item.
- **Household survey count** in numeric QA: "248 households", "248 HH", "household
  survey of 248", "survey sample of 248", "149 + 99 = 248" and "Proposed sample | 248"
  rows, in survey context only; baseline, caseload, indicator-target, historical and
  portfolio numbers stay excluded, and sum parts are never totals.
- **years_experience** only when bound to the candidate's own experience; organisation
  history, project durations, ages and firm tenure yield null. Existing index values
  are re-checked against their stored evidence snippet (no CV re-parse): unsupported
  values become null with `years_experience_status = UNVERIFIED`, and the rejected
  value is kept for provenance.
- Regression tests: `tests/test_v069_south_darfur.py` (+ `tests/fixtures/south_darfur_tor.py`).

---

## [0.6.8] — 2026-11-21

### Fixed — three issues from the first real Fast Mode run (South Darfur)
- **Staff retrieval uses the persisted index.** Team ranking loads the largest
  persisted staff index (user cache, `<ARFADA Knowledge>/.arfada-index/staff_index.json`,
  or `ARFADA_STAFF_INDEX`) instead of whatever subset a session re-scanned, so the
  full pool is searchable without transferring raw CVs. Every CV refresh writes the
  Knowledge-folder copy; a partial cache never shrinks it. New run snapshots freeze
  the full pool. Raw CV text is read only for shortlisted candidates
  (`staff_pool.shortlist_details`). `rank_team` / `fast_proposal.py setup` report
  `searchable_profiles` and the pool source.
- **Numeric QA is section- and entity-aware** (`engine/tor/numeric_claims.py`). Only
  current methodology counts (household survey, KII, FGD, census) are compared, and
  against the run's approved/provisional decisions when present. Experience/Team
  sections, past-project tables, ARFADA portfolio metrics, reference values
  (minimum / baseline / reserve / target) and sub-group mentions are excluded;
  breakdown tables are summed and must equal the stated total. The below-minimum
  decision check uses the same current counts.
- **Assignment-type classifier** (TOR analysis, `context_aware=True`): document title
  and explicit labels weigh most; "end line" (two words) counts as ENDLINE; "baseline"
  used as the comparison dataset no longer scores BASELINE; a final evaluation
  measured against an existing baseline is ENDLINE ("Final (Endline) Evaluation").
  The Writing DNA exemplar scan keeps the legacy scoring unchanged.
- Regression tests: `tests/test_south_darfur_regression.py` (+ synthetic fixture).
- **Team nomination guard + evidence-based ranking** (`lknowledge/staff_doctype.py`,
  `lknowledge/staff_nominate.py`). Each staff profile gets `document_type`
  (CV | SUPPORTING_DOCUMENT | UNKNOWN) and a `cv_likeness_score`, derived from the
  indexed fields and file/folder names (no re-parse; provenance unchanged).
  Fast Mode `rank_team` keeps the base `match_score` and orders by a deterministic
  `nomination_score` (country/pool, CV, TOR role match, parsed roles, theme,
  evaluation/baseline/endline experience, evidenced geography, structured years,
  confidence tie-break) with a per-factor `score_breakdown`. CVs first;
  supporting documents never auto-nominated (still searchable); UNKNOWN only to
  fill; one entry per person. `team_needs_question` is raised only for close top
  candidates, weak evidence or an unconfirmed mandatory lead requirement — and then
  becomes a `team_lead_choice` question inside the 5-question cap.
- Regression tests: `tests/test_team_nomination.py`.

---

## [0.6.7] — 2026-11-21

### Fixed — staff-CV country attribution with nested folders
- A CV's `country` now comes from the FIRST folder directly below `Staff CVs`,
  however deeply it is nested. Previously it used the immediate parent folder,
  so CVs in role/person subfolders were labelled "Senior Evaluation Expert",
  "Team Leader" or a person's name, and country-ranked team selection missed them.
- Expert pools (`International Experts`) set `country_pool`; no country is invented.
- Unambiguous spellings normalized to Master Tracker names (`Palistin` → `Palestine`,
  `Türkiye` → `Turkey`). Unknown top folders are flagged `UNRECOGNIZED_FOLDER`.
- New profile fields: `country_pool`, `source_country_folder`, `country_status`,
  `country_source`. Parsed CV facts and provenance are unchanged.
- Unchanged CVs are re-attributed on refresh without being re-parsed;
  `scripts/repair_staff_country.py` fixes an existing index in place.
- `search_staff` matches canonical country or pool and accepts `strict_country`;
  Fast Proposal team ranking shows each candidate's country.
- Regression tests: `tests/test_staff_country.py`.

---

## [0.6.6] — 2026-11-21

### ARFADA Writing DNA — mandatory writing layer over Fast Proposal Mode

New proposals are newly written but read like ARFADA's own proposal team wrote them,
learned from the 14 indexed TOR↔Proposal pairs. The Fast workflow is unchanged; this
adds a writing layer on top.

- **Persistence** — the corpus + Writing DNA persist under `ARFADA_HOME/exemplars/`
  across chats/runs; if the live folder is unavailable but a valid persisted index
  exists, it is loaded automatically. `fast_proposal.py setup` reports
  `writing_dna.active`, `historical_pairs`, and `relevant_proposals_retrieved`.
- **Relevant-proposal retrieval** (`engine/tor/exemplars/retrieval.py`) — now ranks by
  assignment type, sector, country/region, client/donor, evaluation type, and
  humanitarian/development context (extra dimensions matched as tokens against the
  project-folder name — no re-indexing of the confidential corpus). New
  `relevant_proposals()` returns the closest 2–4 whole proposals; `retrieval_summary()`
  powers the init line.
- **Section-specific style** — generation already retrieves comparable historical
  sections separately (Exec Summary → past Exec Summaries, Methodology → past
  Methodology, …); `prepare_section.py` now passes sector/evaluation-type/thematic.
- **Reduce generic AI writing + Style QA** (`engine/tor/style_qa.py`,
  `scripts/style_qa.py`, `fast_proposal.py style`) — deterministic checks for generic
  filler (robust/comprehensive/holistic/…, "this approach ensures", …), unnatural
  uniformity, excessive headings/bullets, divergence from ARFADA's historical style,
  and suspicious copying, with targeted rewrite suggestions. **Wording only** — never
  changes facts, decisions, methodology numbers, or budget values. A `conformance()`
  score lets regression confirm ARFADA-styled prose out-scores generic templates.
- **Anti-copy** — `anticopy.long_shared_phrases()` surfaces the actual long verbatim
  runs reused from historical proposals (short standard phrases are acceptable); the
  existing 8-gram overlap + entity-leak guards are unchanged and still run in section
  validation and Final QA.
- **Voice priority** — when Writing DNA is active, ARFADA's historical voice takes
  precedence over generic model style, but NEVER over verified facts, approved/
  provisional decisions, methodology numbers, or budget values. Historical proposals
  remain STYLE sources only — never factual authority.

### §Regression
`tests/test_writing_dna.py` uses a synthetic corpus + the Jordan backbone and a South
Darfur scenario: ranking, section-specific retrieval, style QA findings, long-phrase
anti-copy, and the measurable criterion that ARFADA-styled text out-scores generic
templated text while staying newly written.

### Tests: +17 new (Writing DNA layer). Full suite green.

---

## [0.6.5] — 2026-11-21

### Fast Proposal Mode (default UX) — TOR → useful Word draft, fast

The default experience is now **Fast Proposal Mode**: get the user a usable first Word
draft with as few interruptions as possible. Workflow only — the evidence, provenance,
QA, knowledge, and validation engines are unchanged, and every v0.6.4 safety guard is
kept.

- **Autopilot** (`engine/tor/autopilot.py` + `scripts/fast_proposal.py setup`) —
  auto-recommends every decision (assignment type, methodology, sample/FGD/KII,
  timeline, deliverables, section structure), auto-ranks the provisional team and the
  strongest 3–5 past projects (current project excluded), and surfaces **at most 5
  questions** — only where an answer is truly necessary and cannot be safely
  recommended. Emits one compact `proposed_setup.json`, not one card per item.
- **Provisional decisions** (`PROVISIONAL_RECOMMENDATION`) — a new register status:
  evidence-supported, usable in Draft v1, not yet user-approved. Generation uses the
  value (flagged provisional, never an unsupported factual claim); `approve_provisional`
  promotes it to RESOLVED.
- **First output is a DOCX** — `render_docx.py --draft` produces `proposal_draft_v1.docx`
  (client-style, gap-tolerant, "WORKING DRAFT" banner) even if submission evidence is
  still missing. Draft versions bump via `fast_proposal.py next-version`.
- **Blocker taxonomy** (`engine/tor/blockers.py`) — DRAFT_BLOCKER (rare) /
  FINAL_SUBMISSION_BLOCKER / WARNING / IMPROVEMENT. Package/compliance gaps never stop a
  technical draft.
- **Two-status QA** (`engine/tor/fast_qa.py` + `fast_proposal.py status`) —
  `TECHNICAL_DRAFT_STATUS` and `SUBMISSION_PACKAGE_STATUS` reported separately; a
  missing package document makes the package NOT READY without making the draft RED.
  Writes team-only `internal_gaps.md` (never leaked to the client).
- **One-click iteration** — supply a fact / change a decision → regenerate only the
  affected sections → next `proposal_draft_v{N}.docx`, without restarting TOR analysis.

Kept intact: provenance, unsupported-claim prevention, current-project exclusion,
CV-evidence rules, budget reconciliation, client/internal separation, annex validation,
final-export sanitization. RED QA still blocks the FINAL submission, not draft creation.

### §Regression
`tests/test_fast_mode.py` adds a synthetic **South Darfur** conflict-context scenario
and a **Jordan** working-draft scenario: ≤5 questions, provisional recommendations,
`proposal_draft_v1.docx` renders, and a missing registration/package item leaves the
technical draft READY while the submission package is NOT READY.

### Tests: +21 new (Fast Proposal Mode + regressions). Full suite green.

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
