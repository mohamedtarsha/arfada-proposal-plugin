# Changelog

All notable changes to `arfada-proposal` plugin are documented here.

Format: [Semantic Versioning](https://semver.org) — MAJOR.MINOR.PATCH

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
