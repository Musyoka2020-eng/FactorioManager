# Architecture

**Analysis Date:** 2026-04-09

## Pattern Overview

**Overall:** Layered desktop application (Tkinter presentation + service layer + integration clients + local configuration)

**Key Characteristics:**
- UI-first orchestration from a single desktop process in `factorio_mod_manager/main.py`
- Clear package split by responsibility: `factorio_mod_manager/ui/`, `factorio_mod_manager/core/`, `factorio_mod_manager/utils/`
- Background thread and queue usage to keep Tkinter responsive during network and filesystem operations

## Layers

**Presentation Layer (Tkinter UI):**
- Purpose: Render the desktop interface, collect user input, and present operation state.
- Location: `factorio_mod_manager/ui/`
- Contains: `MainWindow`, tab controllers, notification widgets, status queue manager.
- Depends on: `factorio_mod_manager/core/` services and `factorio_mod_manager/utils/` helpers/config.
- Used by: Entry point in `factorio_mod_manager/main.py`.

**Application Logic Layer (UI-Scoped Orchestration):**
- Purpose: Keep operation logic and data presentation separate from widget construction.
- Location: `factorio_mod_manager/ui/checker_logic.py`, `factorio_mod_manager/ui/checker_presenter.py`
- Contains: scan/check/update/delete workflows and filtering/sorting/stat aggregation.
- Depends on: `factorio_mod_manager/core/checker.py`, `factorio_mod_manager/core/mod.py`.
- Used by: `factorio_mod_manager/ui/checker_tab.py`.

**Domain/Service Layer (Mod Operations):**
- Purpose: Implement mod scan, dependency resolution, update checks, and download lifecycle.
- Location: `factorio_mod_manager/core/`
- Contains: `ModChecker`, `ModDownloader`, `FactorioPortalAPI`, `Mod` and `ModStatus` model.
- Depends on: portal HTTP APIs, local zip/filesystem, utility helpers.
- Used by: UI tab controllers (`factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`).

**Infrastructure & Utility Layer:**
- Purpose: Provide app config, logging, and helper functions reused across layers.
- Location: `factorio_mod_manager/utils/`
- Contains: global config singleton, logger setup with queue handler, zip/info parsing, connectivity checks.
- Depends on: standard library + `requests`.
- Used by: entry point, UI, and core services.

## Data Flow

**Startup and UI Composition Flow:**

1. `factorio_mod_manager/main.py` configures DPI awareness and logging (`setup_logger`) and creates Tk root.
2. `MainWindow` in `factorio_mod_manager/ui/main_window.py` builds styles, status bar, and notebook tabs.
3. `StatusManager` starts queue processing and marshals background status events into Tk main-thread updates.
4. User operations on tabs trigger threaded workflows in tab controllers.

**Download Flow (Downloader tab):**

1. User enters mod URL/name in `factorio_mod_manager/ui/downloader_tab.py`.
2. Tab loads metadata via `FactorioPortalAPI` (`factorio_mod_manager/core/portal.py`).
3. `ModDownloader` (`factorio_mod_manager/core/downloader.py`) resolves dependencies recursively.
4. Downloads stream from mirror URLs, validate ZIP integrity, and write files to configured mods directory.
5. Progress/status events are reflected in tab widgets and main status bar.

**Scan and Update Flow (Checker tab):**

1. `CheckerTab` (`factorio_mod_manager/ui/checker_tab.py`) creates `ModChecker` and `CheckerLogic`.
2. `ModChecker.scan_mods()` scans local `*.zip` files and parses embedded `info.json` via `parse_mod_info`.
3. `ModChecker.check_updates()` fetches latest release metadata from Factorio portal in parallel.
4. `CheckerPresenter` filters/sorts status view; selected items trigger update/delete/backup actions.
5. Update path delegates actual download to `ModDownloader` and replaces outdated zip files.

**State Management:**
- In-memory session state in UI and services (for example `CheckerTab.mods`, `ModChecker.mods`, selection sets, transient progress flags).
- Persistent settings in JSON config at `Path.home() / ".factorio_mod_manager" / "config.json"` via `factorio_mod_manager/utils/config.py`.
- Persistent logs in `~/.factorio_mod_manager/logs/app.log` configured in `factorio_mod_manager/main.py` and `factorio_mod_manager/utils/logger.py`.

## Key Abstractions

**Mod Entity (`Mod`):**
- Purpose: Canonical representation of installed/remote mod metadata and version state.
- Examples: `factorio_mod_manager/core/mod.py`
- Pattern: dataclass model with derived properties and status transitions.

**Portal Client (`FactorioPortalAPI`):**
- Purpose: Isolate external Factorio portal calls and dependency parsing.
- Examples: `factorio_mod_manager/core/portal.py`
- Pattern: gateway client with typed error classification (`PortalAPIError`).

**Operation Services (`ModDownloader`, `ModChecker`):**
- Purpose: Encapsulate core workflows for downloads, dependency resolution, scanning, and update checks.
- Examples: `factorio_mod_manager/core/downloader.py`, `factorio_mod_manager/core/checker.py`
- Pattern: stateful service objects with callback hooks for UI progress reporting.

**UI Coordinator Objects (`MainWindow`, tabs, `StatusManager`):**
- Purpose: Build widgets and coordinate async operation results into the main thread.
- Examples: `factorio_mod_manager/ui/main_window.py`, `factorio_mod_manager/ui/status_manager.py`
- Pattern: controller-style UI classes that compose services.

## Entry Points

**CLI/Script Entry Point:**
- Location: `factorio_mod_manager/main.py`
- Triggers: `python -m factorio_mod_manager.main`, direct script execution, and Poetry script `factorio-mod-manager` in `pyproject.toml`.
- Responsibilities: DPI setup, logger and queue initialization, root window creation, app lifecycle handling.

**UI Root Composition:**
- Location: `factorio_mod_manager/ui/main_window.py`
- Triggers: Instantiated by `main()`.
- Responsibilities: global style setup, tab composition, shared notification manager and status manager wiring.

## Error Handling

**Strategy:** Mixed exception propagation with local user-facing fallbacks.

**Patterns:**
- External API errors are normalized by `PortalAPIError` (`factorio_mod_manager/core/portal.py`) with error types such as `offline`, `not_found`, and `timeout`.
- Tab/workflow layers catch exceptions, emit log/status messages, and preserve UI responsiveness (`factorio_mod_manager/ui/checker_logic.py`, `factorio_mod_manager/ui/downloader_tab.py`).
- Entry point catches unhandled exceptions, logs with traceback, then re-raises (`factorio_mod_manager/main.py`).

## Cross-Cutting Concerns

**Logging:** Queue-backed logging pipeline for console/file/UI via `setup_logger` and `QueueHandler` in `factorio_mod_manager/utils/logger.py`.
**Validation:** URL and connectivity checks in `factorio_mod_manager/utils/helpers.py`; portal response status handling in `factorio_mod_manager/core/portal.py`; ZIP integrity checks in `factorio_mod_manager/core/downloader.py`.
**Authentication:** Optional Factorio credentials (`username`/`token`) passed into portal/downloader sessions in `factorio_mod_manager/core/portal.py` and `factorio_mod_manager/core/downloader.py`.

---

*Architecture analysis: 2026-04-09*
