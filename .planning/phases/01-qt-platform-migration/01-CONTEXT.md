# Phase 1: Qt Platform Migration and Behavior Parity — Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the entire `factorio_mod_manager/ui/` layer from Tkinter to PySide6 while preserving all behaviors documented in `PARITY-CHECKLIST.md`. Core logic in `factorio_mod_manager/core/` and utilities in `factorio_mod_manager/utils/` are already framework-agnostic and remain untouched.

**This phase does NOT include:** Fluent glassy redesign (Phase 2), search/filter/settings (Phase 3), queue control (Phase 4), or any new capabilities.

</domain>

<decisions>
## Implementation Decisions

### Code Organization
- **D-01:** Replace-in-place — rewrite `ui/` files directly with Qt code. Keep the same filenames (`main_window.py`, `downloader_tab.py`, `checker_tab.py`, `logger_tab.py`, `widgets.py`, etc.). All imports in other modules continue to point at `factorio_mod_manager.ui.*`.
- **D-02:** Full cutover — no Tkinter fallback, no old Tkinter code kept at end of Phase 1. PROJECT.md already decided this.
- **D-03:** Per-module plans — one plan per UI module (at minimum: main_window, downloader_tab, checker_tab, logger_tab, widgets/notifications). Enables per-piece verification against PARITY-CHECKLIST.md.
- **D-04:** Dependency changes — add `PySide6` to `pyproject.toml` and `requirements.txt`. Remove unused dead-weight deps that Phase 0 confirmed are never imported: `pillow`, `python-dotenv`, `lxml`. Do NOT update PyInstaller spec in Phase 1 (deferred).
- **D-05:** `checker_logic.py` and `checker_presenter.py` are already framework-agnostic (no Tkinter). Agent's discretion on whether to keep them as separate helpers or fold them into the rewritten `checker_tab.py`.

### Threading Model
- **D-06:** QThread + signals/slots — Qt-native approach throughout. Worker threads emit signals; UI slots update widgets on the main thread. This is the cleanest option for Qt's event loop.
- **D-07:** Dedicated QThread subclass per operation type: `DownloadWorker`, `ScanWorker`, `UpdateCheckWorker`. Self-contained, mirrors the existing per-operation thread structure.
- **D-08:** Logger handler and StatusManager approach — agent's discretion. Options include: custom Qt signal emitted from a logging `Handler` subclass, or QTimer-based queue polling. Choose whichever maps cleanest to the existing `QueueHandler` + `StatusManager` patterns.

### Phase 1 Visual Scope
- **D-09:** Reproduce the current dark theme in Qt using a QSS (Qt Style Sheet) global stylesheet. Colors to match: BG `#0e0e0e`, dark panel BG `#1a1a1a`, accent `#0078d4`, accent hover `#1084d7`, text `#e0e0e0`, secondary text `#b0b0b0`, success `#4ec952`, error `#d13438`. Phase 2 will refine and expand the visual system into Fluent glassy.
- **D-10:** Log line colors in the progress console (`LoggerTab`) must be preserved: info = blue, success = green, error = red, warning = yellow.

### Window and Layout Structure
- **D-11:** Top-level window structure — agent's discretion. QMainWindow + QTabWidget is the natural Qt equivalent of the Tkinter root + ttk.Notebook pattern; use this unless there is a strong reason for a different structure.
- **D-12:** Notification/toast system — agent's discretion. The current `NotificationManager` shows floating colored label overlays that fade. Replicate this behavior in whichever Qt mechanism is cleanest (overlay QWidget, custom QFrame, or equivalent). No external toast library required.
- **D-13:** Window startup: launch maximized, minimum size 1100×750 (matching PARITY-CHECKLIST.md startup requirements).

### Agent's Discretion
- `checker_logic.py` / `checker_presenter.py` structural placement (D-05)
- Logger queue-to-Qt bridge approach (D-08)
- StatusManager Qt implementation (D-08)
- QMainWindow vs QWidget root choice (D-11)
- Notification overlay implementation (D-12)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Behavioral Parity Target
- `.planning/phases/00-pre-migration-cleanup/PARITY-CHECKLIST.md` — The authoritative checklist of all ~40 Tkinter behaviors that the Qt migration must replicate. Every PLAN.md verification step must trace back to items in this checklist.

### Codebase Architecture
- `.planning/codebase/STACK.md` — Current technology stack; confirms Tkinter is the only GUI dependency, no third-party Qt bindings exist yet.
- `.planning/codebase/STRUCTURE.md` — Module layout and directory purposes; defines what stays (`core/`, `utils/`) and what is fully replaced (`ui/`).

### Requirements
- `.planning/REQUIREMENTS.md` §Platform Migration — PLAT-01, PLAT-02, PLAT-03 are the three requirements this phase must satisfy.
- `.planning/ROADMAP.md` §Phase 1 — Phase goal, success criteria, and dependency on Phase 0.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (untouched by Phase 1)
- `core/mod.py` — `Mod` dataclass, `ModStatus` enum: used as-is by Qt UI layer
- `core/portal.py` — `FactorioPortalAPI`: drives all portal lookups, unchanged
- `core/downloader.py` — `ModDownloader`: all download/dependency logic, unchanged
- `core/checker.py` — `ModChecker`: all scan/update logic, unchanged
- `utils/config.py` — `Config` singleton: Qt code reads/writes config the same way
- `utils/helpers.py` — `parse_mod_info`, `validate_mod_url`, `is_online`, etc.: unchanged
- `utils/logger.py` — `setup_logger` with `QueueHandler`: needs Qt-friendly queue bridge

### Threading Patterns to Migrate
- `DownloaderTab`: Python thread dispatching progress via `root.after_idle()` callbacks
- `CheckerTab` / `CheckerLogic`: Python threads + `root.after_idle()` for list updates
- `LoggerTab`: daemon thread + `root.after(100, ...)` 100 ms polling loop on `log_queue`
- `StatusManager`: daemon thread + `root.after_idle()` for status bar text updates

### Integration Points
- `main.py` entry point creates `tk.Tk()` → must become `QApplication` + Qt main window
- `setup_logger()` wires a `QueueHandler` to a Python `Queue` → Qt version needs a bridge to `LoggerTab`
- `config.py` singleton is used by both `core/` and `ui/` → no changes needed

</code_context>

<specifics>
## Specific Ideas

- The PARITY-CHECKLIST.md has ~120+ behavioral items across all three tabs. Planner should map each plan's verification section to the relevant checklist items.
- Phase 2 (Fluent shell) builds directly on top of Phase 1's Qt foundation — the QSS stylesheet from Phase 1 becomes the starting point for Phase 2's Fluent redesign. Keep it structured and extractable.
- The `widgets.py` module contains `Notification`, `NotificationManager`, and `PlaceholderEntry` — all need Qt equivalents. `PlaceholderEntry` maps to `QLineEdit` with placeholder text built-in.

</specifics>

<deferred>
## Deferred Ideas

- PyInstaller spec update for PySide6 — user deferred; handle in a post-Phase 1 pass or as part of packaging work.
- Fluent glassy visual system — Phase 2.
- The unused `pillow`, `python-dotenv`, `lxml` dependency removal is included in D-04 (add PySide6 + clean dead deps).

</deferred>

---

*Phase: 01-qt-platform-migration*
*Context gathered: 2026-04-10*
