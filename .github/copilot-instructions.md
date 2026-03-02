# Project: Armenian Anki Note Generation Pipelines

## Environment & Running Commands

- **OS**: Windows 11, PowerShell 5.1
- **Python**: 3.12.3 via conda `base` environment
- **Python is NOT on PATH** without conda activation. Every terminal must activate conda first:
  ```powershell
  (C:\Users\litni\anaconda3\shell\condabin\conda-hook.ps1) ; (conda activate base)
  ```
- After activation, `python` works normally for the rest of that terminal session.
- **Project root**: `C:\Users\litni\OneDrive\Documents\anki\anki-note-generation-pipelines` (on OneDrive)

## Common Commands

| Task | Command |
|------|---------|
| Run tests | `python -m pytest` |
| Run a module | `python -m wa_corpus.build_corpus --help` |
| Anki data export | `python _pull_anki_data.py` |
| Card generation | `python generate_anki_cards.py` |
| Build corpus (wiki) | `python -m wa_corpus.build_corpus --wiki` |
| Build corpus (newspapers) | `python -m wa_corpus.build_corpus --newspapers` |
| Build corpus (IA) | `python -m wa_corpus.build_corpus --ia` |

## AnkiConnect

- REST API on **localhost:8765** (Anki desktop must be running with AnkiConnect add-on)
- Profile name: `armenians_global`
- Anki data directory: `%APPDATA%\Anki2\` (standard location, NOT on OneDrive)
- Wrapper: `armenian_anki/anki_connect.py`
- **READ-ONLY by default** — do not modify Anki data without explicit user permission

## Key Directories

- `armenian_anki/` — Core package (morphology, card gen, progression, DB, AnkiConnect)
- `wa_corpus/` — Western Armenian frequency corpus tools (wiki, newspapers, IA, nayiri scrapers)
- `wa_corpus/data/` — Downloaded corpus data (gitignored, large)
- `anki_media/` — Exported media files from Anki (gitignored)
- `anki_export.json` — Full Anki note export (gitignored)
- `extracted_text_simple/` — OCR extraction output

---

# Session Tracking Instructions

After every conversation compaction (context window reset), update the session progress file at `/memories/session/session-progress.md` with the following:

1. **What was accomplished** — List each task completed since the last update, with specific results (numbers, file names, outcomes). Group by topic area.

2. **Clarifying questions & answers** — Maintain a table of every question the user asked during the session and the answer/finding. Format as a markdown table with Question and Answer columns.

3. **Key findings** — Any technical discoveries, verifications, or facts learned during the session that might need to be referenced later (e.g., API endpoints, tool versions, config values, confirmed behaviors).

4. **Current state** — What's in progress, what's blocked, and what the immediate next step is.

5. **Remaining work** — Checklist of outstanding tasks with `[ ]` / `[x]` markers.

## Rules

- Append new information rather than overwriting previous sections (so the file becomes a running log).
- Be specific — include counts, file paths, error messages, and concrete outcomes rather than vague summaries.
- If a previous finding was wrong or updated, note the correction explicitly.
- Do this automatically on every compaction without being asked.
