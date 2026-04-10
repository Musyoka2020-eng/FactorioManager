# Codebase Structure

**Analysis Date:** 2026-04-09

## Directory Layout

```text
FactorioManager/
├── factorio_mod_manager/        # Application package (entry, UI, domain logic, utilities)
│   ├── core/                    # Mod domain services and external API client
│   ├── ui/                      # Tkinter window/tab controllers and custom widgets
│   └── utils/                   # Shared config, helpers, and logging
├── .planning/                   # GSD planning artifacts and codebase analysis docs
│   └── codebase/                # Generated mapping docs (STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE)
├── build/                       # PyInstaller intermediate build artifacts
├── dist/                        # Built executable output artifacts
├── pyproject.toml               # Poetry metadata, dependencies, script entry point
├── requirements.txt             # pip dependency list
├── README.md                    # User/developer documentation
├── FactorioModManager.spec      # PyInstaller build specification
└── FactorioModManager.iss       # Inno Setup installer script
```

## Directory Purposes

**factorio_mod_manager/:**
- Purpose: Root Python package for runtime application code.
- Contains: startup module, three functional subpackages, package `__init__.py`.
- Key files: `factorio_mod_manager/main.py`, `factorio_mod_manager/__init__.py`.

**factorio_mod_manager/ui/:**
- Purpose: Presentation layer and UI interaction orchestration.
- Contains: main window, tab controllers, presentation helpers, thread-safe status manager, custom widgets.
- Key files: `factorio_mod_manager/ui/main_window.py`, `factorio_mod_manager/ui/downloader_tab.py`, `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/status_manager.py`.

**factorio_mod_manager/core/:**
- Purpose: Domain/service logic for portal access, dependency resolution, download execution, and update checks.
- Contains: API client, downloader, checker, dataclass model, package exports.
- Key files: `factorio_mod_manager/core/portal.py`, `factorio_mod_manager/core/downloader.py`, `factorio_mod_manager/core/checker.py`, `factorio_mod_manager/core/mod.py`.

**factorio_mod_manager/utils/:**
- Purpose: Shared infrastructure utilities consumed by UI and core packages.
- Contains: config management, helper functions, logger setup.
- Key files: `factorio_mod_manager/utils/config.py`, `factorio_mod_manager/utils/helpers.py`, `factorio_mod_manager/utils/logger.py`.

**.planning/codebase/:**
- Purpose: Generated architecture and stack documentation used by GSD planning commands.
- Contains: markdown summaries of stack, integration, architecture, and structure.
- Key files: `.planning/codebase/STACK.md`, `.planning/codebase/INTEGRATIONS.md`.

**build/ and dist/:**
- Purpose: Packaging outputs from PyInstaller build process.
- Contains: generated binaries/intermediate files, not core source.
- Key files: `build/FactorioModManager/*`, `dist/*`.

## Key File Locations

**Entry Points:**
- `factorio_mod_manager/main.py`: Runtime bootstrap and Tkinter app launch.
- `pyproject.toml`: Declares script `factorio-mod-manager = "factorio_mod_manager.main:main"`.

**Configuration:**
- `factorio_mod_manager/utils/config.py`: JSON config persistence and mods-folder auto-detection.
- `pyproject.toml`: Dependency and packaging configuration.
- `requirements.txt`: pip-based dependency pin set.
- `FactorioModManager.spec`: executable packaging behavior.

**Core Logic:**
- `factorio_mod_manager/core/portal.py`: Factorio mod portal API client + dependency parsing.
- `factorio_mod_manager/core/downloader.py`: dependency traversal + download/ZIP validation.
- `factorio_mod_manager/core/checker.py`: local scan and update workflow.
- `factorio_mod_manager/core/mod.py`: `Mod` data model and status enum.

**Testing:**
- Not detected: no `tests/` directory and no `*.test.*` or `*.spec.*` source test files found in repository tree.

## Naming Conventions

**Files:**
- Python modules use snake_case naming (for example `main_window.py`, `checker_presenter.py`, `status_manager.py`).
- Package entry/export files use `__init__.py`.

**Directories:**
- Package folders use lowercase names (`factorio_mod_manager`, `core`, `ui`, `utils`).
- Build/tooling directories use conventional names (`build`, `dist`, `.planning`).

## Where to Add New Code

**New Feature:**
- Primary code: put UI-facing behavior in `factorio_mod_manager/ui/` and business/service logic in `factorio_mod_manager/core/`.
- Tests: create a new `tests/` directory at repository root (not currently present) with mirrored package paths.

**New Component/Module:**
- Implementation: place Tkinter views/controllers under `factorio_mod_manager/ui/`; place portal/download/check workflows under `factorio_mod_manager/core/`.

**Utilities:**
- Shared helpers: add reusable helpers and infra support into `factorio_mod_manager/utils/`.
- Export shared symbols through `factorio_mod_manager/utils/__init__.py` when they are intended as package-level API.

## Special Directories

**.planning/:**
- Purpose: Planning metadata and generated analysis docs.
- Generated: Yes (tool-generated content expected).
- Committed: Yes (present in repository working tree).

**build/:**
- Purpose: PyInstaller build intermediates.
- Generated: Yes.
- Committed: Yes (currently present in repository working tree).

**dist/:**
- Purpose: distributable application artifacts.
- Generated: Yes.
- Committed: Yes (currently present in repository working tree).

**.venv/:**
- Purpose: local virtual environment and interpreter packages.
- Generated: Yes.
- Committed: No expectation in source control workflows (environment-local).

---

*Structure analysis: 2026-04-09*
