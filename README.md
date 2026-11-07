# ARFADA Proposal Plugin

A Claude Code plugin for ARFADA staff. Brings structured TOR analysis and
proposal drafting into Claude Code — distributed privately via GitHub.

> **Status:** Phase 2 — TOR Analysis + Human Decision Review.
> Proposal generation planned for Phase 3.

---

## What it does

| Phase | Version | Capability |
|-------|---------|-----------|
| 0 | 0.1.x | Plugin shell, GitHub distribution |
| 1 | 0.2.x | TOR analysis: requirements, metadata, decisions (EN + AR, PDF + DOCX) |
| 2 | 0.3.x | **Human Decision Review: record proposal choices, validate against TOR** |
| 3 | 1.0.0 | Full TOR-to-proposal draft generation |

### Current capabilities (v0.3.0)

1. **Analyze TOR** — extract requirements, metadata, constraints, and decision
   candidates from a `.pdf` or `.docx` TOR (English + Arabic, tables, provenance).
2. **Review Proposal Decisions** — walk through genuine proposal decisions one by
   one, record the team's choices (validated against TOR constraints), defer to
   inception, or leave unresolved. Resumable, editable, fully traceable.

---

## Installation (team members)

Requires: Claude Code + access to `mohamedtarsha/arfada-proposal-plugin` (private)

```bash
# 1. Add the ARFADA marketplace (once per machine)
claude plugin marketplace add mohamedtarsha/arfada-proposal-plugin

# 2. Install the plugin
claude plugin install arfada-proposal@arfada
```

Then restart Claude Code (or start a new session). The skill is live immediately.

### Python dependencies

TOR analysis needs a few document-parsing libraries (see `requirements_plugin.txt`):

```bash
pip install python-docx pypdf pdfplumber
```

No API key required — all analysis is deterministic Python; Claude Code's active
session handles presentation and conversation.

---

## Usage

```
/arfada-proposal
```

Claude will respond as ARFADA Proposal Assistant and walk you through
the available options for the current plugin version.

---

## Updating

```bash
# Pull latest version from GitHub
claude plugin marketplace update arfada

# Then restart Claude Code or start a new session
```

> Auto-update is DISABLED by default for private marketplaces.
> Run the update command manually when a new version is released.

---

## Versioning policy

- `0.x.y` — pre-release phases, iterative engine integration
- `1.0.0` — first full proposal pipeline (TOR → draft)
- `MAJOR` — breaking change to skill interface
- `MINOR` — new capability (new subcommand or engine connection)
- `PATCH` — fix or wording improvement

Version is authoritative in `.claude-plugin/plugin.json`.

---

## Security rules

This repository **does not and must not contain**:

| Forbidden | Why |
|-----------|-----|
| `.env` files | Contains API keys |
| TOR documents | Confidential client material |
| Proposal drafts | Client IP |
| `*.db`, `*.duckdb` | Internal project data |
| Google service-account JSON | Live credentials |
| VPS SSH keys | Infrastructure access |

The `.gitignore` enforces these rules.

---

## Developer reference (manual install fallback)

For development or if CLI install is not available:

```bash
git clone https://github.com/mohamedtarsha/arfada-proposal-plugin.git
xcopy /E /I "arfada-proposal-plugin\skills\arfada-proposal" "%USERPROFILE%\.claude\skills\arfada-proposal"
```

This path is a developer fallback only. The team workflow is the marketplace commands above.

---

## Repository

Private. ARFADA staff only. See `NOTICE` for redistribution policy.
