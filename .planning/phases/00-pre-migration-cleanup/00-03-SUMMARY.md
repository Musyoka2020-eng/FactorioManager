---
plan: 00-03
phase: 00-pre-migration-cleanup
status: complete
tasks_completed: 1
tasks_total: 1
commits:
  - 0cff76c
key-files:
  created:
    - .planning/phases/00-pre-migration-cleanup/PARITY-CHECKLIST.md
---

# Plan 00-03 Summary: Behavioral Parity Checklist for Qt Migration

## What Was Built

Created `.planning/phases/00-pre-migration-cleanup/PARITY-CHECKLIST.md` — a comprehensive behavioral acceptance test document derived directly from `.planning/codebase/FEATURES.md`.

The checklist contains **125 verifiable items** across 8 sections:
1. Application Startup (8 items)
2. Tab 1 — Downloader (27 items — layout, auto-search, Load Mod, Browse, Download, progress, results)
3. Tab 2 — Checker & Updates (43 items — layout, buttons, scan, selection, check, update, delete, backup, details, search/filter)
4. Tab 3 — Logs (9 items)
5. Notifications System (6 items)
6. Status Bar (5 items)
7. Configuration Persistence (3 items)
8. Behaviors NOT to replicate (2 items — Tkinter bugs to leave behind)

All items are formatted as `- [ ]` checkboxes with specific, manually verifiable pass/fail criteria. Phase 1 PREP-03 (download button re-enable after offline failure) and PREP-04 (Clear button in Logs) are explicitly called out as required behaviors in the Qt version.

## Verification Results

- `PASS: 125 checklist items, 236 lines` — exceeds the 30-item, 80-line minimums
- All FEATURES.md section behaviors map to at least one checklist item
- "Behaviors NOT to replicate" section lists Tkinter threading and error-swallowing bugs

## Self-Check: PASSED

All acceptance criteria met:
- File exists at correct path
- 125 `- [ ]` items (≥ 30 required)
- 236 lines (≥ 80 required)
- Sections present: Startup, Downloader, Checker, Logs, Notifications, Status Bar, Config, Bugs NOT to replicate
- Each item is specific enough for manual verification
- PREP-03 and PREP-04 explicitly referenced
