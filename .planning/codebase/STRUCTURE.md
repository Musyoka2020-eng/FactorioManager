# Codebase Structure

**Analysis Date:** 2026-04-10

## Directory Layout

```
FactorioManager/                          # Project root
├── factorio_mod_manager/                 # Main application package
│   ├── __init__.py
│   ├── main.py                           # Entry point — DPI, logging, tk.Tk bootstrap
│   ├── core/                             # Business logic (no Tkinter)
│   │   ├── __init__.py                   # Re-exports: ModChecker, ModDownloader, Mod, ModStatus
│   │   ├── mod.py                        # Mod dataclass, ModStatus enum, FACTORIO_EXPANSIONS
│   │   ├── portal.py                     # FactorioPortalAPI, PortalAPIError
│   │   ├── downloader.py                 # ModDownloader (dependency resolution + re146 download)
│   │   └── checker.py                    # ModChecker (scan, update-check, update, 10-min cache)
│   ├── ui/                               # All Tkinter code
│   │   ├── __init__.py                   # Re-exports: MainWindow
│   │   ├── main_window.py                # MainWindow — root window, notebook, header, status bar
│   │   ├── downloader_tab.py             # DownloaderTab — URL input, metadata, download UI
│   │   ├── checker_tab.py                # CheckerTab — 3-column grid, mod list rendering
│   │   ├── checker_logic.py              # CheckerLogic — thread-safe operations for checker tab
│   │   ├── checker_presenter.py          # CheckerPresenter — filtering, sorting, statistics
│   │   ├── logger_tab.py                 # LoggerTab — real-time log viewer (queue polling)
│   │   ├── status_manager.py             # StatusManager — queue-based status bar dispatcher
│   │   └── widgets.py                    # Notification, NotificationManager, PlaceholderEntry
│   └── utils/                            # Cross-cutting utilities
│       ├── __init__.py                   # Re-exports: config, helpers, logger
│       ├── config.py                     # Config class + module-level singleton `config`
│       ├── helpers.py                    # parse_mod_info, format_file_size, validate_mod_url, is_online
│       └── logger.py                     # setup_logger (file + queue handler)
├── build/                                # PyInstaller build artifacts (not committed)
│   └── FactorioModManager/
├── .planning/                            # GSD planning documents
│   └── codebase/                         # Auto-generated codebase docs
├── pyproject.toml                        # Project metadata and build config
├── requirements.txt                      # Runtime dependencies
├── FactorioModManager.spec               # PyInstaller spec file
├── FactorioModManager.iss                # Inno Setup installer script
└── README.md
```

## Directory Purposes

**`factorio_mod_manager/core/`:**
- Purpose: All business logic — completely independent of Tkinter
- Contains: Data models, HTTP clients, file I/O, dependency resolver
- Key files:
  - `mod.py` — `Mod` dataclass, `ModStatus` enum
  - `portal.py` — `FactorioPortalAPI` (reads `mods.factorio.com/api/mods/{name}/full`)
  - `downloader.py` — `ModDownloader` (recursive dep resolution, re146.dev download, ZIP validation)
  - `checker.py` — `ModChecker` (scan folder, concurrent portal fetch, update/delete mods, cache)
- Rule: No Tkinter imports. All progress output goes through `progress_callback` callable.

**`factorio_mod_manager/ui/`:**
- Purpose: All Tkinter widget construction and user interaction
- Contains: Window, tabs, helper widgets, threading glue
- Key files:
  - `main_window.py` — `MainWindow` (root window owner, passes `StatusManager` and `NotificationManager` to tabs)
  - `downloader_tab.py` — `DownloaderTab` (URL debounce, metadata display, per-mod sidebar, download thread)
  - `checker_tab.py` — `CheckerTab` (3-column layout: left settings+buttons, center mod list, right stats+filter+sort)
  - `checker_logic.py` — `CheckerLogic` (thread worker calls; no Tkinter)
  - `checker_presenter.py` — `CheckerPresenter` (pure static methods; no Tkinter)
  - `logger_tab.py` — `LoggerTab` (100 ms poll of `log_queue`, colored log lines)
  - `status_manager.py` — `StatusManager` (daemon thread + `after_idle` dispatch to status bar)
  - `widgets.py` — `Notification`, `NotificationManager`, `PlaceholderEntry`

**`factorio_mod_manager/utils/`:**
- Purpose: Shared helpers used by both `core/` and `ui/`
- Key files:
  - `config.py` — `Config` class; `config` singleton persisted at `~/.factorio_mod_manager/config.json`
  - `helpers.py` — `parse_mod_info(zip_path)` reads `info.json` from inside a mod ZIP; `format_file_size`, `validate_mod_url`, `is_online`
  - `logger.py` — `setup_logger(name, log_queue, log_file)` wires `QueueHandler` + `RotatingFileHandler`

**`build/`:**
- Purpose: PyInstaller output — generated, not committed
- Generated: Yes
- Committed: No

**`.planning/codebase/`:**
- Purpose: GSD codebase mapping documents consumed by plan/execute agents
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Yes (planning artifacts)

## Key File Locations

**Entry Point:**
- `factorio_mod_manager/main.py` — `main()` function; run directly or via `pyproject.toml` script entry

**Configuration:**
- `factorio_mod_manager/utils/config.py` — `Config` class and `config` singleton
- `~/.factorio_mod_manager/config.json` — runtime user config (persisted outside repo)
- `pyproject.toml` — project metadata, dependencies, PyInstaller target
- `requirements.txt` — pinned runtime deps (`requests`, `beautifulsoup4`, etc.)

**Core Logic:**
- `factorio_mod_manager/core/portal.py` — Factorio portal HTTP client
- `factorio_mod_manager/core/downloader.py` — dependency resolution + download
- `factorio_mod_manager/core/checker.py` — scan + update-check + update workflow
- `factorio_mod_manager/core/mod.py` — `Mod` data model

**UI Entry:**
- `factorio_mod_manager/ui/main_window.py` — `MainWindow` (owns root `tk.Tk`, all tabs, status bar)

**Testing:**
- No test directory exists — see TESTING.md

## Naming Conventions

**Files:**
- All snake_case: `downloader_tab.py`, `checker_logic.py`, `status_manager.py`
- Tab UI files: `{feature}_tab.py`
- Presenter/logic split: `checker_presenter.py`, `checker_logic.py`

**Classes:**
- PascalCase: `ModDownloader`, `CheckerPresenter`, `FactorioPortalAPI`, `NotificationManager`
- Tab classes follow pattern `{Feature}Tab` (e.g., `DownloaderTab`, `CheckerTab`, `LoggerTab`)

**Functions/methods:**
- snake_case throughout
- Private widget builders prefixed with `_`: `_setup_ui()`, `_create_header()`, `_setup_styles()`
- Background work prefixed with `_run_` or `_start_`: `_run_scan()`, `_start_download()`

**Variables:**
- Tkinter `StringVar`/`BooleanVar` suffixed with `_var`: `folder_var`, `filter_var`, `include_optional_var`
- Widget references stored on `self` with descriptive names: `self.scan_btn`, `self.mod_info_text`, `self.status_label`

**Constants:**
- Module-level color constants in UPPER_SNAKE_CASE on each tab class: `BG_COLOR = "#0e0e0e"`, `ACCENT_COLOR = "#0078d4"`

## Where to Add New Code

**New feature in the download workflow:**
- Business logic: `factorio_mod_manager/core/downloader.py` (add method to `ModDownloader`)
- UI wiring: `factorio_mod_manager/ui/downloader_tab.py`

**New feature in the checker/update workflow:**
- Business logic: `factorio_mod_manager/core/checker.py` (add method to `ModChecker`)
- Thread wrapper: `factorio_mod_manager/ui/checker_logic.py` (add method to `CheckerLogic`)
- Display logic: `factorio_mod_manager/ui/checker_presenter.py` (add static method if pure data transform)
- UI wiring: `factorio_mod_manager/ui/checker_tab.py`

**New tab:**
- Create `factorio_mod_manager/ui/{name}_tab.py` with a class `{Name}Tab`
- Register in `factorio_mod_manager/ui/main_window.py` inside `__init__` after existing tabs
- Export from `factorio_mod_manager/ui/__init__.py` if needed

**New custom widget:**
- Add to `factorio_mod_manager/ui/widgets.py`

**New utility helper:**
- Add to `factorio_mod_manager/utils/helpers.py`
- Export from `factorio_mod_manager/utils/__init__.py`

**New configuration key:**
- Add to `Config.DEFAULTS` dict in `factorio_mod_manager/utils/config.py`

**New core entity/data model:**
- Add to `factorio_mod_manager/core/mod.py` or create a new file in `core/`
- Export from `factorio_mod_manager/core/__init__.py`

---

*Structure analysis: 2026-04-10*
