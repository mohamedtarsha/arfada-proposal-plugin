# ARFADA Proposal Plugin

A Claude Code plugin for ARFADA staff. Brings structured TOR analysis and
proposal drafting into Claude Code — distributed privately via GitHub.

> **Status:** COMPLETE (v0.6.0) — TOR Analysis → Decision Review → Local Knowledge →
> Controlled Generation → Professional Word → **Final Quality Review (GREEN/YELLOW/RED)**.
> Core development done; the plugin is in team use. Future work = small bugfixes +
> real-TOR tuning from actual usage.

### Final Quality Review (v0.6.0)

`final_qa.py <run_dir>` runs deterministic acceptance over all artifacts — requirement
coverage (verified against real content), decision compliance, ARFADA fact support,
numeric contradictions, framework/deliverables/workplan/team/submission, and
client-DOCX leakage — and returns **GREEN / YELLOW / RED**. `export_final.py` gates the
final client DOCX: GREEN exports, YELLOW needs `--confirm`, RED is blocked. GREEN means
"ready for final **human** review", never "send blind". No API, no VPS, no MCP.

### ARFADA knowledge (v0.5.2) — local folder, OAuth-free

ARFADA operational data (Master Tracker, staff CVs, company docs, brand) is read
from a single **local folder** you choose — which may be a Google Drive for Desktop /
OneDrive / Dropbox / network-mounted folder. The plugin only sees a filesystem path:
**no OAuth, no Google API, no VPS, no MCP, no Anthropic API**. Setup:
`knowledge_folder.py set "<path>"` → `refresh_knowledge.py` → generate. Metrics come
from `Master Tracker.xlsx` (deterministic), CVs are indexed recursively, and each
proposal run freezes an **immutable snapshot**. The static `knowledge/` snapshot is
an explicit **STATIC_FALLBACK**. The Google OAuth connector remains available but
**optional/advanced**. See SKILL "ARFADA Knowledge" for the full workflow.

---

## What it does

| Phase | Version | Capability |
|-------|---------|-----------|
| 0 | 0.1.x | Plugin shell, GitHub distribution |
| 1 | 0.2.x | TOR analysis: requirements, metadata, decisions (EN + AR, PDF + DOCX) |
| 2 | 0.3.x | Human Decision Review: record proposal choices, validate against TOR |
| 3 | 0.4.x | Controlled proposal draft generation (TOR-grounded, decision-aware) |
| 4 | 0.5.x | **Assignment-type inference + verified ARFADA knowledge + professional DOCX** |
| 5 | 1.0.0 | Final quality review |

### Current capabilities (v0.5.0)

1. **Analyze TOR** — requirements, metadata, constraints, decision candidates, and
   **assignment-type inference** (Evaluation / Needs Assessment / TPM / Research / …
   with confidence + evidence; LOW confidence surfaces a classification decision —
   no fixed "evaluation" default). English + Arabic, PDF + DOCX, tables, provenance.
2. **Review Proposal Decisions** — record the team's choices, validated against TOR
   constraints; resumable, editable, traceable.
3. **Generate Proposal Draft** — deterministic **type-specific** blueprint (the
   framework section is an Evaluation / Assessment / Monitoring / Research matrix as
   appropriate), requirement ownership, response slots, decision dependencies. The
   active Claude Code session writes each section (no API key). **Verified ARFADA
   facts** (versioned local knowledge snapshot) are injected with provenance; the
   validator rejects unsupported ARFADA claims (`UNSUPPORTED_ARFADA_CLAIM`) and
   requires `NEEDS_ARFADA_EVIDENCE` placeholders for anything unverified.
4. **Export Word** — professional editable `.docx` (python-docx only, no MS Word /
   LibreOffice) with a cover page, named styles, real headings, bullet/numbered
   lists, and real Word tables. Two variants: **internal review** (shows evidence
   gaps + provenance) and **client draft** (hides all internal metadata; blocked if
   a hard unsupported-fact error remains).

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
