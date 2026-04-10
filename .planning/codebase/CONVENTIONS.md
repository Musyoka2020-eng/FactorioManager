# Coding Conventions

**Analysis Date:** 2026-04-10

## Naming Patterns

**Files:**
- Use `snake_case.py` for module filenames (examples: `factorio_mod_manager/core/downloader.py`, `factorio_mod_manager/ui/checker_presenter.py`).
- Use package directories by concern (`core`, `ui`, `utils`) under `factorio_mod_manager/`.
- UI tab modules correlate 1:1 with class name: `checker_tab.py` → `CheckerTab`, `downloader_tab.py` → `DownloaderTab`.

**Functions:**
- Use `snake_case` for functions and methods (examples: `enable_dpi_awareness`, `set_progress_callback`, `resolve_dependencies`).
- Prefix internal helpers with `_` for private intent (examples: `_log_progress`, `_setup_ui`, `_browse_folder`).
- Setup helpers use `_setup_*` convention: `_setup_ui()`, `_setup_styles()`.
- Tkinter event handlers use `_on_*` convention: `_on_tab_visible()`, `_on_mousewheel()`.

**Variables:**
- Use `snake_case` for local variables and instance attributes (examples: `last_update_check`, `mod_progress_callback`, `folder_var`).
- Use `UPPER_SNAKE_CASE` for module/class constants (examples: `FACTORIO_EXPANSIONS` in `factorio_mod_manager/core/mod.py`, `BG_COLOR` in `factorio_mod_manager/ui/main_window.py`).
- Tkinter `StringVar` / `BooleanVar` attributes use `self.noun_var` form: `self.folder_var`, `self.filter_var`, `self.filter_mode`.
- Boolean state flags use `is_*` prefix: `self.is_scanning`, `self.is_downloading`.

**Types:**
- Use `PascalCase` for classes and dataclasses (`Mod`, `ModChecker`, `CheckerPresenter`, `StatusManager`).
- Use `Enum` for bounded status values (`ModStatus` in `factorio_mod_manager/core/mod.py`).
- Use modern Python 3.12 generic syntax: `tuple[bool, str]`, `list[str]`, `dict[str, Mod]` (not `Tuple`, `List`, `Dict` from `typing`).

## Code Style

**Formatting:**
- Tool declared: Black (`black ^23.12.0`) in `pyproject.toml`.
- Key settings: No project-specific Black config detected; default 88-char line length applies.

**Linting:**
- Tool declared: Ruff (`ruff ^0.1.0`) in `pyproject.toml`.
- Key rules: No explicit Ruff configuration section detected in `pyproject.toml`.

## Import Organization

**Order:**
1. Standard library imports first (`pathlib`, `typing`, `concurrent.futures`, `tkinter`).
2. Third-party imports next (`requests`, `bs4`).
3. Local package imports last (`from ..core import ...`, `from .widgets import ...`).

**Example from `factorio_mod_manager/ui/checker_tab.py`:**
```python
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from typing import Dict, List, Optional
from threading import Thread
from pathlib import Path
from ..core import ModChecker, Mod, ModStatus
from ..utils import config, format_file_size, is_online
from .widgets import PlaceholderEntry, NotificationManager
from .checker_logic import CheckerLogic
from .checker_presenter import CheckerPresenter
```

**Path Aliases:**
- Not used. Imports are package-relative or absolute package imports.
- `factorio_mod_manager/main.py` prepends project root to `sys.path` for script execution.

**Lazy imports inside functions** are used to avoid circular imports or defer heavy platform-specific imports:
- `import platform` inside `Config._detect_factorio_folder()` in `factorio_mod_manager/utils/config.py`
- `import shutil` inside `CheckerLogic.clean_backups()` in `factorio_mod_manager/ui/checker_logic.py`

## Error Handling

**Custom exception:** `PortalAPIError` (`factorio_mod_manager/core/portal.py`) is the only domain-specific exception. Always raise it for any portal-level failure — never raise a bare `Exception` from `portal.py` or `downloader.py`. It carries:
- `message` — user-facing string
- `error_type` — one of `"offline"`, `"not_found"`, `"server_error"`, `"timeout"`, `"unknown"`
- `status_code` — optional HTTP integer

**Anti-pattern to avoid:** Bare `except:` blocks exist in Tkinter scroll-binding callbacks to mute Tcl widget-destruction errors. This is acceptable only there; **never use bare `except:` in business logic**.

**Re-raise convention:**
```python
# Inside portal.py / downloader.py — re-raise custom errors unchanged:
except PortalAPIError:
    raise
except Exception as e:
    raise PortalAPIError(f"Error: {str(e)}", error_type="unknown")
```

**Where to catch:** At the UI boundary only — inside `_start_scan()`, `_start_check()`, `update_mods()` in tab classes. Core layer (`factorio_mod_manager/core/`, `factorio_mod_manager/ui/checker_logic.py`) raises; UI layer catches and surfaces messages to users.

**Config loading** uses broad `except Exception as e: print(...)` with graceful fallback to defaults — acceptable only in `factorio_mod_manager/utils/config.py`.

## Logging

**Framework:** Python `logging` plus queue-backed UI sink in `factorio_mod_manager/utils/logger.py`.

**Setup:** Call `setup_logger()` once in `factorio_mod_manager/main.py`. Pass `log_queue` and `log_file` to get all three outputs (console, file, UI log tab).

**QueueHandler:** `factorio_mod_manager/utils/logger.py` — `QueueHandler(logging.Handler)` puts formatted strings into a `Queue` for `LoggerTab` to consume.

**Logger names:** Use `logging.getLogger("factorio_mod_manager")` at app root; use `logging.getLogger(__name__)` in submodules.

**Log file location:** `~/.factorio_mod_manager/logs/app.log`

**Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s` with `datefmt="%Y-%m-%d %H:%M:%S"`.

**Three distinct progress channels — use the right one:**

| Channel | Method | Destination |
|---------|--------|-------------|
| Structured app log | `self.logger.info/error(...)` | File + Logs tab |
| UI progress console | `self._log_progress(msg, level)` | Colored `tk.Text` in tab |
| Status bar | `status_manager.push_status(msg, type)` | Bottom status bar only |

**`_log_progress` level strings:** `"info"`, `"success"`, `"error"`, `"warning"` — map directly to text tag colors.

## Comments

**When to Comment:**
- Use short comments to explain operational intent and non-obvious branches (for example OS-specific DPI handling in `factorio_mod_manager/main.py`).
- Multi-line explanatory comments are used for domain constraints (for example expansion handling in `factorio_mod_manager/core/mod.py`).

**Docstrings:**
- All public classes and methods carry Google-style docstrings with `Args:` and `Returns:` sections.
- Private helpers may omit docstrings if their name and signature are self-explanatory.

## UI Patterns

**Thread safety — the queue/after() contract:**
Background worker threads MUST NOT touch Tkinter widgets directly. The approved pattern:
1. Worker pushes to a `Queue` or calls `status_manager.push_status(msg, type)`.
2. Main thread polls via `root.after(100, poll_fn)` every 100ms, or receives via `root.after_idle(callback)`.
3. `StatusManager` (`factorio_mod_manager/ui/status_manager.py`) runs a daemon thread that drains `status_queue` and marshals back with `root.after_idle(lambda: update_callback(msg, type))`.

**Known bug — do not replicate:** Some progress text inserts are made directly from worker threads (a threading violation). Never add new direct widget mutations from non-main threads.

**Callback registration on `ModDownloader` (`factorio_mod_manager/core/downloader.py`):**
```python
downloader.set_progress_callback(cb)          # cb(message: str) → progress console text
downloader.set_overall_progress_callback(cb)  # cb(completed: int, total: int) → progress bar + status bar
downloader.set_mod_progress_callback(cb)      # cb(mod_name: str, status: str, pct: float) → per-mod sidebar
```

**Tag-based text formatting in `tk.Text`:**
Progress/log consoles use named tags:
```python
text_widget.tag_config("info",    foreground="#0078d4")  # blue
text_widget.tag_config("success", foreground="#4ec952")  # green
text_widget.tag_config("error",   foreground="#d13438")  # red
text_widget.tag_config("warning", foreground="#ffad00")  # yellow
# Insert with tag:
text_widget.insert("end", message + "\n", "success")
```
Both the Downloader progress console and Checker operation log use this pattern with `Consolas` font.

**Notification system:** `NotificationManager` (`factorio_mod_manager/ui/widgets.py`) overlays the root window. Main window injects the shared instance via `tab.set_notification_manager(manager)`. Tabs call `self._notify(msg, type, duration_ms)`.

**Config auto-save:** Browse buttons save immediately — `config.set(key, value)` (which calls `config.save()`) is called inside the browse callback, not on form submit.

**Live search:** `tk.StringVar.trace("w", callback)` fires on every keystroke. Calls `CheckerPresenter.filter_mods()` which is pure (no side effects). Case-insensitive match on name, title, and author.

**Sort and filter:** `CheckerPresenter.filter_mods()` accepts `sort_by` ("name", "version", "downloads", "date") and `filter_mode` ("all", "outdated", "up_to_date", "selected"). Filter buttons arranged 2×2 in Checker tab.

**Multi-select:** Ctrl+click pattern for mod list — tracked in `self.selected_mods: set` on `CheckerTab`.

**Auto-scan on tab visibility:** `CheckerTab` binds `"<Visibility>"` event via `self.frame.bind("<Visibility>", self._on_tab_visible)`.

**Tkinter styles:** All `ttk` styles configured in `MainWindow._setup_styles()` using `ttk.Style()` with `clam` theme. Style names: `"Dark.TFrame"`, `"Card.TFrame"`, `"Header.TLabel"`, `"Small.TLabel"`, `"Accent.TButton"`.

**Grid vs pack:** `CheckerTab` three-column layout uses `.grid()`. Single-axis header/footer regions use `.pack()`. Never mix `grid` and `pack` on children of the same parent widget.

## Color & Style Constants

Color constants are class attributes on each tab class. They are duplicated across `MainWindow`, `DownloaderTab`, and `CheckerTab` — treat `MainWindow` (`factorio_mod_manager/ui/main_window.py`) as the authoritative source.

| Constant        | Value       | Usage                                      |
|-----------------|-------------|--------------------------------------------|
| `BG_COLOR`      | `#0e0e0e`   | Root window and canvas backgrounds         |
| `DARK_BG`       | `#1a1a1a`   | Card / section panel backgrounds           |
| `ACCENT_COLOR`  | `#0078d4`   | Primary buttons, separator lines           |
| `ACCENT_HOVER`  | `#1084d7`   | Button hover state                         |
| `FG_COLOR`      | `#e0e0e0`   | Primary text                               |
| `SECONDARY_FG`  | `#b0b0b0`   | Secondary / dimmed text                    |
| `SUCCESS_COLOR` | `#4ec952`   | Success states, up-to-date status badges   |
| `ERROR_COLOR`   | `#d13438`   | Error states, failed status badges         |
| `WARNING_COLOR` | `#ffad00`   | Outdated status, warning labels            |

Font families used: `"Segoe UI"` for all UI text; `"Courier New"` for file path labels; `"Consolas"` for progress consoles and operation logs.

**Mod status lifecycle in UI:** `"Preparing..."` → `"Downloading..."` → `"✓ Downloaded"` or `"✗ Failed"` (per-mod sidebar in Downloader tab).

## Practical Guidance For New Code

- Keep new modules in `snake_case` and classes in `PascalCase`.
- Add type hints and Google-style docstrings to all new public methods.
- Raise `PortalAPIError` in `core/`; catch and display in `ui/` only.
- Route progress through callbacks or the logging queue — never mutate widgets from worker threads.
- Continue using `factorio_mod_manager/core/__init__.py` and `factorio_mod_manager/utils/__init__.py` barrel exports for stable import surfaces.
- Duplicate color constants match `MainWindow` values — update all three class definitions together.

---

*Convention analysis: 2026-04-10*
