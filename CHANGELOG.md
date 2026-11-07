# Changelog

All notable changes to `arfada-proposal` plugin are documented here.

Format: [Semantic Versioning](https://semver.org) — MAJOR.MINOR.PATCH

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
