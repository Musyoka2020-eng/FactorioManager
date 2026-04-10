---
plan: 00-02
phase: 00-pre-migration-cleanup
status: complete
tasks_completed: 2
tasks_total: 2
commits:
  - b268a06
  - 1d248f2
key-files:
  modified:
    - factorio_mod_manager/ui/downloader_tab.py
    - factorio_mod_manager/ui/logger_tab.py
---

# Plan 00-02 Summary: Fix Download Button Disable Bug + Wire Clear Button

## What Was Built

Fixed two standalone bugs in the Tkinter UI to ensure behavioral correctness before Qt migration:

1. **Download button re-enable after offline check failure (PREP-03)** — `_start_download()` was disabling the Download button and setting `is_downloading = True` before the offline connectivity check. When offline, the method returned early without re-enabling the button, leaving the user unable to retry downloads without restarting the app. Added `self.is_downloading = False` and `self.download_btn.config(state="normal")` immediately before the early `return` in the offline guard block.

2. **Clear button wired to `LoggerTab.clear_logs()` (PREP-04)** — The `clear_logs()` method already existed but was not reachable from the UI. Added a toolbar frame at the top of the `LoggerTab` widget tree (packed before the scrollbar and text widget) with a right-aligned "Clear" button that calls `self.clear_logs`. This gives users a way to clear the log display without restarting.

## Verification Results

- `python -m py_compile` passes for both files
- `PASS: download button fix present` — `is_downloading = False` and `download_btn.config(state="normal")` confirmed in offline check block
- `PASS: Clear button wired to clear_logs()` — `command=self.clear_logs` confirmed in logger_tab.py

## Self-Check: PASSED

All acceptance criteria met:
- `downloader_tab.py` re-enables button before the offline return
- `logger_tab.py` has a Clear button with `command=self.clear_logs`
- Both files compile without errors
- `_download_thread` finally block is unchanged (verified by inspection)
