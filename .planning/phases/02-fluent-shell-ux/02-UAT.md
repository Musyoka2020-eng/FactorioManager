---
status: testing
phase: 02-fluent-shell-ux
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md]
started: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
---

## Current Test

number: 4
name: Left Rail Navigation — No Tabs
expected: |
  When the app launches, the main navigation should use a vertical left rail with
  icon/label buttons (Downloader, Checker, Logs, Settings), NOT a horizontal tab
  bar across the top. Clicking each nav item should switch to the corresponding page.
awaiting: user response

## Tests

### 1. Fluent QSS Selectors Present
expected: All required selectors (navRail, navItem, pageHeader, pageTitle, infoCard, sidePanel, categoryChip) present in dark_theme.qss
result: pass
notes: auto-verified — all 7 selectors confirmed in generated stylesheet

### 2. Inline Style Purge Complete (Phase 2 scope)
expected: No disallowed setStyleSheet calls in main_window.py, downloader_tab.py, checker_tab.py, logger_tab.py (allowed exceptions: widgets.py dynamic color, main.py app stylesheet)
result: pass
notes: auto-verified — Phase 2 scope files are clean; mod_details_dialog.py (Phase 3 file) has one inline style — tracked as Phase 3 tech debt

### 3. Notification Severity Durations + Event-Key Dedup
expected: NotificationManager has _SEVERITY_DURATIONS map and event_key deduplication logic
result: pass
notes: auto-verified — _SEVERITY_DURATIONS and event_key dedup code confirmed in widgets.py

### 4. Left Rail Navigation — No Tabs
expected: |
  The main navigation uses a vertical left rail with icon/label buttons, NOT a
  horizontal tab bar. Clicking each nav item switches to the corresponding page.
result: [pending]

### 5. Page Headers Visible on All Screens
expected: |
  Each page (Downloader, Checker, Logs) shows a visible header zone at the top with
  the page title. The headers should look consistent across all three pages.
result: [pending]

### 6. Downloader — Two-Panel Browse/Detail Layout
expected: |
  The Downloader page shows a left panel (search bar + category chips + results list)
  and a right "Selected Mod" detail panel. The two panels are separated by a draggable
  splitter. No staged step-by-step flow requiring clicking through stages.
result: [pending]

### 7. Checker — Page Header with Scan CTA
expected: |
  The Checker/Updates page has a header zone at the top with the title and a primary
  action button (e.g., "Scan" or "Check Updates"). The header should be visually
  distinct from the content area below it.
result: [pending]

### 8. Logs — Page Header with Clear Button in Header
expected: |
  The Logs page has a header zone with the page title AND a "Clear" button visible
  in the header area (not just in the log area below). Clicking it clears the log.
result: [pending]

### 9. Toast — Severity Affects Duration
expected: |
  Trigger an info notification (e.g., any mild status message) and then trigger a
  warning or error (e.g., attempt to download without a folder). The error/warning
  toast should stay visible noticeably longer than a routine info toast.
result: [pending]

## Summary

total: 9
passed: 3
issues: 0
pending: 6
skipped: 0

## Gaps

[none yet]
