# Coding Conventions

**Analysis Date:** 2026-04-09

## Naming Patterns

**Files:**
- Use `snake_case.py` for module filenames (examples: `factorio_mod_manager/core/downloader.py`, `factorio_mod_manager/ui/checker_presenter.py`).
- Use package directories by concern (`core`, `ui`, `utils`) under `factorio_mod_manager/`.

**Functions:**
- Use `snake_case` for functions and methods (examples: `enable_dpi_awareness`, `set_progress_callback`, `resolve_dependencies`).
- Prefix internal helpers with `_` for private intent (examples: `_log_progress`, `_download_with_re146`, `_setup_ui`).

**Variables:**
- Use `snake_case` for local variables and instance attributes (examples: `last_update_check`, `mod_progress_callback`, `folder_var`).
- Use `UPPER_SNAKE_CASE` for module/class constants (examples: `FACTORIO_EXPANSIONS` in `factorio_mod_manager/core/mod.py`, `BG_COLOR` in `factorio_mod_manager/ui/main_window.py`).

**Types:**
- Use `PascalCase` for classes and dataclasses (`Mod`, `ModChecker`, `CheckerPresenter`, `StatusManager`).
- Use `Enum` for bounded status values (`ModStatus` in `factorio_mod_manager/core/mod.py`).

## Code Style

**Formatting:**
- Tool declared: Black (`black`) in `pyproject.toml`.
- Key settings: No project-specific Black config detected in `pyproject.toml`; default Black behavior is implied.

**Linting:**
- Tool declared: Ruff (`ruff`) in `pyproject.toml`.
- Key rules: No explicit Ruff configuration section detected in `pyproject.toml`.

## Import Organization

**Order:**
1. Standard library imports first (`pathlib`, `typing`, `concurrent.futures`, `tkinter`).
2. Third-party imports next (`requests`, `bs4`).
3. Local package imports last (`from ..core import ...`, `from .widgets import ...`).

**Path Aliases:**
- Not used. Imports are package-relative or absolute package imports.
- `factorio_mod_manager/main.py` prepends project root to `sys.path` for script execution.

## Error Handling

**Patterns:**
- Catch broad exceptions at integration boundaries and convert to user-facing messages.
- Use custom exception type for API context (`PortalAPIError` in `factorio_mod_manager/core/portal.py`) with `error_type` and optional `status_code`.
- Re-raise after logging at top-level app boundary (`factorio_mod_manager/main.py`).
- UI/business layers commonly log and then re-raise to preserve failure propagation.

Code example from `factorio_mod_manager/core/portal.py`:
```python
try:
    response = self.session.get(f"{self.API_URL}/{mod_name}/full", timeout=10)
    if response.status_code == 404:
        raise PortalAPIError(
            f"Mod '{mod_name}' not found on the portal",
            error_type="not_found",
            status_code=404,
        )
except requests.exceptions.ConnectionError:
    raise PortalAPIError(
        "Cannot connect to Factorio portal. Check your internet connection.",
        error_type="offline",
    )
```

## Logging

**Framework:** Python `logging` plus queue-backed UI sink in `factorio_mod_manager/utils/logger.py`.

**Patterns:**
- Initialize one app logger through `setup_logger` and share by name (`factorio_mod_manager`).
- Use `QueueHandler` to forward formatted log lines into UI queue.
- Use progress callback methods (`_log_progress`) in core services; fallback to `print` if callback is absent.

Code example from `factorio_mod_manager/utils/logger.py`:
```python
logger = logging.getLogger(name)
logger.setLevel(level)

if not logger.handlers:
    logger.addHandler(console_handler)

if log_queue:
    ui_handler = QueueHandler(log_queue)
    logger.addHandler(ui_handler)
```

## Comments

**When to Comment:**
- Use short comments to explain operational intent and non-obvious branches (for example OS-specific DPI handling in `factorio_mod_manager/main.py`).
- Multi-line explanatory comments are used for domain constraints (for example expansion handling in `factorio_mod_manager/core/mod.py`).

**JSDoc/TSDoc:**
- Not applicable (Python codebase).
- Python docstrings are used consistently at module, class, and function level.

## Function Design

**Size:**
- UI builder methods are large and monolithic (for example `_setup_ui` in `factorio_mod_manager/ui/checker_tab.py` and `factorio_mod_manager/ui/downloader_tab.py`).
- Core methods in `core/` are medium-to-large and task-focused (download/resolve/check/update workflows).

**Parameters:**
- Use explicit typed parameters with defaults for optional behavior (`Optional[...]`, boolean flags such as `force_refresh`, `include_optional`).
- Callback injection is common (`Callable` callbacks for progress/status updates).

**Return Values:**
- Favor structured returns via tuples and dictionaries over side effects alone.
- Common patterns: `(result, status_flag)` and `(success_list, failed_list)` tuples.

Code example from `factorio_mod_manager/core/checker.py`:
```python
def check_updates(self, force_refresh: bool = False) -> tuple[Dict[str, Mod], bool]:
    ...
    return outdated, was_refreshed
```

## Module Design

**Exports:**
- Package-level export curation via `__all__` in `factorio_mod_manager/core/__init__.py` and `factorio_mod_manager/utils/__init__.py`.
- Cross-layer usage mostly imports from package init modules rather than deep internals.

**Barrel Files:**
- Present and used (`factorio_mod_manager/core/__init__.py`, `factorio_mod_manager/utils/__init__.py`).

## Design Patterns In Use

**Callback/Observer-like updates:**
- Core services expose callback setters for progress and UI updates (`set_progress_callback`, `set_mod_progress_callback`, `set_overall_progress_callback` in `factorio_mod_manager/core/downloader.py`).

**Presenter pattern (UI separation):**
- Data shaping and filtering are extracted to `CheckerPresenter` (`factorio_mod_manager/ui/checker_presenter.py`).

**Logic/UI split:**
- `CheckerLogic` isolates thread and operation logic away from widget rendering (`factorio_mod_manager/ui/checker_logic.py`).

**Thread-safe queue communication:**
- `StatusManager` and logger queue pass cross-thread updates back to Tk main thread (`factorio_mod_manager/ui/status_manager.py`, `factorio_mod_manager/ui/logger_tab.py`).

## Practical Guidance For New Code

- Keep new modules and functions in `snake_case` and classes in `PascalCase`.
- Add type hints and docstrings to all new public methods.
- Prefer raising domain-specific exceptions in `core/` and handling them in `ui/` with user-readable status text.
- Route operational progress through callbacks or logging queue, not direct widget mutation from worker threads.
- Continue using package `__init__.py` exports for stable import surfaces.

---

*Convention analysis: 2026-04-09*
