# ARFADA Proposal Plugin

A Claude Code plugin for ARFADA staff that brings structured TOR analysis and
proposal drafting into Claude Code.

> **Status:** Phase 0 — plugin shell validated.
> Proposal engine integration begins in Phase 1.

---

## What it does

| Phase | Version | Capability |
|-------|---------|-----------|
| 0 | 0.1.x | Plugin shell, TOR receipt, version reporting |
| 1 | 0.2.x | RAG search over ARFADA archive |
| 2 | 0.3.x | Cited paragraph generation |
| 3 | 1.0.0 | Full TOR-to-proposal draft |

---

## Installation

### Prerequisites
- [Claude Code](https://claude.ai/code) installed and authenticated
- Access to the private `arfada-proposal-plugin` GitHub repository

### Install

```bash
claude plugin install https://github.com/mohamedtarsha/arfada-proposal-plugin
```

Or manually (alternative):

```bash
# Clone the repo somewhere on your machine
git clone https://github.com/mohamedtarsha/arfada-proposal-plugin.git

# Copy the skill into Claude Code's user skills directory
# Windows:
xcopy /E /I "arfada-proposal-plugin\skills\arfada-proposal" "%USERPROFILE%\.claude\skills\arfada-proposal"

# Mac/Linux:
cp -r arfada-proposal-plugin/skills/arfada-proposal ~/.claude/skills/arfada-proposal
```

---

## Usage

Type in any Claude Code conversation:

```
/arfada-proposal
```

Claude will respond as ARFADA Proposal Assistant and walk you through the
available options for the current plugin version.

---

## Updating

### Via plugin command (recommended)

```bash
claude plugin update arfada-proposal
```

### Manually

```bash
cd arfada-proposal-plugin
git pull origin main
xcopy /E /I /Y "skills\arfada-proposal" "%USERPROFILE%\.claude\skills\arfada-proposal"
```

Then **restart Claude Code** (or reload: `/reload`).

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

The `.gitignore` enforces these rules. If you accidentally stage a sensitive
file, run `git reset HEAD <file>` before committing.

---

## Repository

Private. ARFADA staff only.
See `NOTICE` for redistribution policy.
