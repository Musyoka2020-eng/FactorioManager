# Technology Stack

**Analysis Date:** 2026-04-10

## Languages

**Primary:**
- Python 3.12+ — all application code under `factorio_mod_manager/`

## Runtime

**Environment:**
- CPython 3.12 (minimum, per `pyproject.toml` constraint `^3.12`)

**Package Manager:**
- Poetry (`pyproject.toml`)
- Pip-compatible pinned lockfile: `requirements.txt` (used for PyInstaller builds)

## Frameworks

**GUI:**
- `tkinter` (stdlib) — entire desktop UI in `factorio_mod_manager/ui/`; no third-party GUI framework
- `ttk` (stdlib themed widgets) — used throughout tabs and widgets

**HTTP Client:**
- `requests ^2.32.0` — API calls (`portal.py`) and direct file downloads (`downloader.py`)
  - `requests.Session` used for portal API calls (auth stub attached but never invoked — see INTEGRATIONS.md)
  - Plain `requests.get()` used for actual mod downloads in `_download_with_re146()`; bypasses Session entirely

**HTML Parsing:**
- `beautifulsoup4 ^4.12.0` — parses mod changelog HTML at `https://mods.factorio.com/mod/{name}/changelog`
  - Parser backend: Python stdlib `html.parser` (NOT lxml; `BeautifulSoup(response.text, 'html.parser')`)
  - Used only in `factorio_mod_manager/core/portal.py` — `get_mod_changelog()`

## Testing

**Runner:**
- `pytest ^7.4.0` (dev dependency)
- No test files detected in the current workspace

## Code Quality

**Formatter:**
- `black ^23.12.0` (dev dependency)

**Linter:**
- `ruff ^0.1.0` (dev dependency)

## Build & Packaging

**Executable bundling:**
- PyInstaller — spec file at `FactorioModManager.spec`; build artefacts under `build/FactorioModManager/`
- Entry point: `factorio_mod_manager/main.py` → `main()`

**Windows installer:**
- Inno Setup — script at `FactorioModManager.iss`

## Key Dependencies

**Critical (actively used):**
| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | ^2.32.0 | Portal API queries + streaming mod file downloads |
| `beautifulsoup4` | ^4.12.0 | Changelog HTML scraping (`portal.py`) |

**Declared but unused — safe to remove:**
| Package | Version | Notes |
|---------|---------|-------|
| `pillow` | ^10.1.0 | Never imported anywhere in `factorio_mod_manager/` |
| `python-dotenv` | ^1.0.0 | Never imported; no `.env` file loading in codebase |
| `lxml` | ^4.9.0 | Never imported; BeautifulSoup explicitly uses `html.parser`, not lxml |
| `selenium` | ^4.25.0 | Listed in `pyproject.toml` only (absent from `requirements.txt`); never imported |

## Configuration

**Runtime config:**
- JSON file: `~/.factorio_mod_manager/config.json` — managed by `factorio_mod_manager/utils/config.py`
- Keys: `mods_folder`, `username`, `token`, `theme`, `auto_backup`, `download_optional`, `auto_refresh`, `max_workers`
- No `.env` file support despite `python-dotenv` being listed as a dependency

**Build:**
- `pyproject.toml` — Poetry project and dependency declaration
- `FactorioModManager.spec` — PyInstaller bundling specification
- `FactorioModManager.iss` — Inno Setup Windows installer script

## Platform Requirements

**Development:**
- Python 3.12 or later
- Windows / Linux / macOS (tkinter is cross-platform)

**Production:**
- Windows — primary target; packaged as standalone `.exe` via PyInstaller + Inno Setup
- Linux/macOS — supported via source install; no packaged distribution provided

---

*Stack analysis: 2026-04-10*
