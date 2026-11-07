---
name: arfada-proposal
description: >
  ARFADA Proposal Assistant — structured TOR analysis and proposal drafting for
  ARFADA team members. Invoke with /arfada-proposal to analyze a TOR, review
  extracted requirements, check decisions, and prepare for proposal writing.
version: 0.2.2
trigger: /arfada-proposal
---

# ARFADA Proposal Assistant

**Plugin version:** 0.2.2
**Publisher:** ARFADA
**Status:** Phase 1 — TOR Analysis active

---

## Menu (when invoked without a TOR file)

Print exactly:

```
ARFADA Proposal Assistant v0.2.0

Available now:
  1. Analyze TOR  — provide a .pdf or .docx file

Coming later:
  2. Review Proposal Decisions
  3. Generate Proposal Draft
  4. Quality Review
  5. Export Word
```

Then ask:

> Do you have a TOR file to analyze? Provide the full file path (.pdf or .docx).

---

## TOR Analysis Workflow

### Step 1 — Accept the TOR file

If the user provides a file path in any form:
- `/arfada-proposal` followed by a file path
- A file path given in reply to the menu prompt
- A file path given directly in the first message

Extract the file path. If it contains spaces and is not quoted, reconstruct it
from context. Use the path exactly as provided.

Do NOT ask for the path again if already given.

### Step 2 — Run the analysis script

Use the Bash tool to run:

```bash
python "<plugin_root>/scripts/analyze_tor.py" "<file_path>"
```

Where `<plugin_root>` is the directory containing this plugin (the directory
containing `scripts/`, `engine/`, `skills/`). Determine it from the location
of this SKILL.md file: it is two levels up (skills/arfada-proposal/SKILL.md →
plugin root).

The script outputs lines like:
```
OUTPUT_DIR=C:\path\to\arfada-output\tor_20261107_010438
RUN_ID=tor_20261107_010438
REQUIREMENTS=63
MANDATORY=48
DECISIONS=7
DELIVERABLES=6
```

Parse these values.

If the script fails (non-zero exit), report the error clearly and stop.

### Step 3 — Read the analysis summary

Use the Read tool to read:

```
<OUTPUT_DIR>/analysis_summary.md
```

Also read:

```
<OUTPUT_DIR>/tor_analysis.json
```

to get the full structured data for follow-up questions.

### Step 4 — Present the analysis

Format and present:

```
ARFADA TOR Analysis — [file name]

Assignment:     [metadata.assignment.value or NOT_SPECIFIED]
Client:         [metadata.client.value or NOT_SPECIFIED]
Country:        [metadata.country.value or NOT_SPECIFIED]

Requirements:
  Total:                [total_requirements]
  Mandatory:            [mandatory]
  Optional:             [optional]
  Human decisions:      [human_decisions]
  Bidder obligations:   [bidder_obligations]
  Client responsibilities: [client_responsibilities]

Extracted Objects:
  Deliverables:         [deliverables]
  Timeline items:       [timeline_items]
  Submission items:     [submission_items]
  Team requirements:    [team_items]
  Evaluation questions: [eval_questions]
  Methodology items:    [methodology_items]

Output: [OUTPUT_DIR]
```

### Step 5 — List decisions

After the summary, always show:

```
Decisions Required ([human_decisions]):
```

Then list each `is_human_decision: true` requirement from requirements.json,
showing: `[ID excerpt] text — reason`.

If no decisions: state "No open decisions detected."

### Step 6 — Offer drill-down

After the summary and decisions, offer:

```
You can ask:
  • "show mandatory requirements"
  • "show submission requirements"
  • "show deliverables"
  • "show team requirements"
  • "show evaluation questions"
  • "show [category] requirements"
  • "show requirement [ID]"
  • "show client responsibilities"
  • "export summary"
```

---

## Drill-Down Responses

For any follow-up request to show a category:

1. Read `<OUTPUT_DIR>/requirements.json` if not already in context.
2. Filter by category, actor, or decision flag as requested.
3. Present each matching requirement as:
   ```
   [ID] [mandatory/optional] [actor]
   Text: ...
   Section: ...
   ```
4. For requirement detail by ID: show full text, source section, page (if available),
   provenance locator, decision flag and note.

---

## Multiple TOR Sessions

If the user provides a new file path in the same session:
- Run a new analysis.
- Keep the previous OUTPUT_DIR available if the user asks to compare.

---

## Constraints

- NEVER invent requirement text not in the JSON.
- NEVER assign a page number not present in the JSON.
- NEVER claim a requirement is mandatory if the JSON says mandatory=false.
- Do NOT commit TOR files or output directories to Git.
- Output directories (arfada-output/) are local only — do not share paths externally.
- If the user asks to "save" or "export": write to the existing output directory
  (already created by the script). Do NOT create new output locations.
- For Arabic TOR: note that the current engine uses English modal patterns —
  Arabic obligation language detection is limited; a future version will improve this.

---

## Error Handling

**File not found:**
> File not found at the given path. Please check the path and try again.

**Unsupported format:**
> Only .pdf and .docx files are supported. Convert the TOR to one of these formats.

**Script error:**
> Analysis failed: [error message]. Check that python-docx and pypdf are installed
> in the Python environment used by Claude Code.

**No requirements found:**
> No requirements were extracted. This may indicate a heavily scanned PDF or an
> unusual document structure. Try a .docx version if available.
