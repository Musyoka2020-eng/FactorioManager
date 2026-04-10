# Architecture

**Analysis Date:** 2026-04-10

## Pattern Overview

**Overall:** Layered desktop application — thin UI layer over a pure-Python core, with strict separation between business logic and presentation.

**Key Characteristics:**
- `core/` is completely UI-agnostic; all classes accept callback functions for progress reporting rather than importing Tkinter
- `ui/` modules own all Tkinter widget construction; they call into `core/` via worker threads
- A presenter/logic split in the Checker tab extracts filtering/sorting (`CheckerPresenter`) and thread operations (`CheckerLogic`) from the raw widget code (`CheckerTab`)
- Status bar updates are decoupled from calling code via a queue-based `StatusManager` — but per-tab widget state mutations happen directly from worker threads (known inconsistency)

## Layers

**Entry Point:**
- Purpose: Bootstrap — DPI awareness, logging, queue wiring, root window creation
- Location: `factorio_mod_manager/main.py`
- Contains: `main()`, `enable_dpi_awareness()`
- Depends on: All layers below
- Used by: Nothing (top-level script)

**UI Layer:**
- Purpose: All Tkinter widget construction, event binding, and user interaction
- Location: `factorio_mod_manager/ui/`
- Contains: `MainWindow`, `DownloaderTab`, `CheckerTab`, `LoggerTab`, `CheckerLogic`, `CheckerPresenter`, `StatusManager`, `NotificationManager`, `Notification`
- Depends on: `core/`, `utils/`
- Used by: `main.py`

**Core Layer:**
- Purpose: Business logic — mod scanning, dependency resolution, downloading, portal API
- Location: `factorio_mod_manager/core/`
- Contains: `ModChecker`, `ModDownloader`, `FactorioPortalAPI`, `Mod`, `ModStatus`
- Depends on: `utils/`, external HTTP (`requests`, `beautifulsoup4`)
- Used by: `ui/`

**Utils Layer:**
- Purpose: Cross-cutting helpers — configuration, file parsing, formatting, connectivity checks
- Location: `factorio_mod_manager/utils/`
- Contains: `Config` (singleton `config`), `parse_mod_info`, `format_file_size`, `validate_mod_url`, `is_online`, `setup_logger`
- Depends on: stdlib only
- Used by: `core/`, `ui/`

## Data Flow

### Startup Flow

1. `main()` calls `enable_dpi_awareness()` (Windows DPI via `ctypes.windll.shcore.SetProcessDpiAwareness(2)`)
2. Creates `log_queue = Queue()` and passes it to `setup_logger()`, which attaches a `QueueHandler` so every log record is mirrored into the queue
3. Creates `tk.Tk()` root window, then `MainWindow(root, log_queue=log_queue)`
4. `MainWindow.__init__` builds the widget tree in order: styles → `NotificationManager` → header (dark `#1a1a1a` bar + `#0078d4` 2 px separator) → main container → `ttk.Notebook` → status bar → `StatusManager.start()` → `DownloaderTab` → `CheckerTab` → `LoggerTab`
5. `StatusManager.start()` spawns a daemon thread that blocks on `status_queue.get(timeout=0.1)` and routes each `(message, type)` tuple back to the main thread via `root.after_idle()`
6. `LoggerTab._poll_logs()` schedules itself every 100 ms via `frame.after(100, self._poll_logs)` and drains `log_queue` with `get_nowait()` on each poll
7. Window is set to state `zoomed` (maximized); minimum size is 900×600, geometry hint 1100×750
8. `root.mainloop()` begins the Tk event loop

### Download Flow

1. User types a URL into `DownloaderTab.url_entry`; each `<KeyRelease>` schedules `_schedule_search()` with a 500 ms debounce timer
2. After debounce fires, `FactorioPortalAPI.get_mod(mod_name)` is called (hits `https://mods.factorio.com/api/mods/{name}/full`)
3. Response populates the `mod_info_text` metadata panel (title, author, version, description, dependencies)
4. User clicks **Load Mod** → `_load_dependencies()` runs `ModDownloader.resolve_dependencies()` recursively; each dependency calls `portal.get_mod()`; results populate a per-mod sidebar
5. User clicks **Download** → `_start_download()` launches a `Thread(target=self._run_download)`
6. Worker thread calls `ModDownloader.download_mods(mod_names, include_optional=...)`, which:
   a. Re-resolves the full dependency tree (deduplication via `visited` set prevents cycles)
   b. Warns about incompatibilities and expansion (DLC) requirements in the progress log
   c. Calls `download_mod()` per mod → `_download_with_re146()` fetches from `https://mods-storage.re146.dev/{name}/{version}.zip`
   d. Streams response in 8 KB chunks; calls `progress_callback` at intervals
   e. Validates downloaded bytes as a ZIP using `zipfile.ZipFile.testzip()`; deletes file on failure
   f. Writes final file to `{mods_folder}/{name}_{version}.zip`
7. Per-mod sidebar rows transition: "Preparing…" → "Downloading…" → "✓ Downloaded" / "✗ Failed" via `mod_progress_callback` — **these widget writes happen directly from the worker thread** (threading bug)

### Scan / Update Check Flow

1. When the Checker tab first becomes visible, `<Visibility>` fires `_on_tab_visible()`, which schedules `_start_scan()` after 3 000 ms via `frame.after(3000, ...)` (one-shot, guarded by `auto_scan_scheduled` flag)
2. `_start_scan()` launches `Thread(target=self._run_scan)`
3. Worker thread calls `CheckerLogic.scan_mods()` → `ModChecker.scan_mods()`:
   a. Globs `mods_folder` for `*.zip` files (first pass — parse filenames + read `info.json` from each archive via `parse_mod_info()`)
   b. Second pass: submits all mod names to `ThreadPoolExecutor(max_workers=4)` that calls `FactorioPortalAPI.get_mod()` concurrently
   c. `as_completed()` collects results; each `Mod.latest_version` is set and `update_status()` is called
   d. `last_update_check` timestamp is saved
4. Worker thread calls back into UI to render results — **direct widget mutation from the worker thread** (threading bug)
5. `CheckerPresenter.get_statistics()` counts totals by `ModStatus` value and returns `Dict[str, int]`
6. User clicks **Check Updates** → `CheckerLogic.check_updates(force_refresh)`:
   - If `last_update_check` was < 10 minutes ago and `force_refresh=False`, returns cached `mods` dict without network calls
   - Otherwise calls `ModChecker.scan_mods()` to re-fetch portal data
7. User clicks **Update Selected** → `CheckerLogic.update_mods(mod_names)` → `ModChecker.update_mods()` → `ModDownloader.download_mod()` per mod (same re146.dev path)
8. **Delete** → `CheckerLogic.delete_mods()` resolves each mod's file as `{mods_folder}/{name}_{version}.zip`, calls `Path.unlink()`, removes entry from `ModChecker.mods` dict
9. **Clean Backups** → `CheckerLogic.clean_backups(backup_folder)` calculates folder size, calls `shutil.rmtree()`, returns freed MB

## Key Abstractions

**`Mod` (dataclass):**
- Purpose: Single source of truth for a mod's local and portal state
- Location: `factorio_mod_manager/core/mod.py`
- Key fields: `name`, `version`, `latest_version`, `status: ModStatus`, `dependencies`, `optional_dependencies`, `incompatible_dependencies`, `expansion_dependencies`, `file_path`, `downloads`, `file_size`
- Key behavior: `update_status()` compares `version` vs `latest_version` using integer-tuple comparison; sets `status` to `OUTDATED` or `UP_TO_DATE`

**`ModStatus` (Enum):**
- Values: `UP_TO_DATE`, `OUTDATED`, `UNKNOWN`, `ERROR`
- Location: `factorio_mod_manager/core/mod.py`
- Used by: `CheckerPresenter.STATUS_COLORS`, `CheckerPresenter.filter_mods()`, `CheckerPresenter.get_statistics()`

**`FactorioPortalAPI`:**
- Location: `factorio_mod_manager/core/portal.py`
- Fetches metadata from `https://mods.factorio.com/api/mods/{name}/full` (10 s timeout)
- Parses dependency strings: `!` prefix = incompatible, `(?)`/`?` prefix = optional, no prefix = required; `FACTORIO_EXPANSIONS` set (`space-age`, `elevated-rails`) routes paid-DLC deps to a separate list
- Raises `PortalAPIError(message, error_type, status_code)`; typed `error_type` values: `"offline"`, `"not_found"`, `"server_error"`, `"timeout"`, `"unknown"`

**`ModDownloader`:**
- Location: `factorio_mod_manager/core/downloader.py`
- Dependency resolution: `resolve_dependencies(mod_name, include_optional, visited)` — recursive, `visited: Set[str]` prevents cycles
- Download target: `https://mods-storage.re146.dev/{name}/{version}.zip` (no Factorio credentials required)
- Three callback hooks: `progress_callback` (text log lines), `mod_progress_callback` (per-mod sidebar), `overall_progress_callback` (aggregate count)

**`ModChecker`:**
- Location: `factorio_mod_manager/core/checker.py`
- Aggregates `FactorioPortalAPI` + `ModDownloader`
- Holds `mods: Dict[str, Mod]` as in-memory cache with `last_update_check: Optional[datetime]`
- 10-minute cache freshness threshold in `check_updates()`

**`CheckerPresenter` (static methods):**
- Location: `factorio_mod_manager/ui/checker_presenter.py`
- Pure data transformation — no Tkinter imports
- `filter_mods(mods, search_query, filter_mode, selected_mods, sort_by)` → `List[tuple[str, Mod]]`
- `filter_mode` values: `"all"`, `"outdated"`, `"up_to_date"`, `"selected"`
- `sort_by` values: `"name"`, `"version"`, `"downloads"`, `"date"`
- `get_statistics()` → `Dict[str, int]`; `format_statistics_multiline()` → `List[tuple[str, str]]`

**`CheckerLogic`:**
- Location: `factorio_mod_manager/ui/checker_logic.py`
- Thin orchestrator wrapping `ModChecker`; calls `self.logger` (the tab's `_log_progress` callable) on each meaningful event
- No Tkinter imports; designed to be called from worker threads

**`Config` (singleton `config`):**
- Location: `factorio_mod_manager/utils/config.py` — imported as module-level `config = Config()`
- Persists to `~/.factorio_mod_manager/config.json`
- Auto-detects mods folder on first run (Windows: `%APPDATA%\Roaming\Factorio\mods`, Linux: `~/.factorio/mods`, macOS: `~/Library/Application Support/factorio/mods`)
- Keys: `mods_folder`, `username`, `token`, `theme`, `auto_backup`, `download_optional`, `auto_refresh`, `max_workers`

## Threading Model

The application uses two distinct patterns but applies them inconsistently.

### Correct pattern — StatusManager

`StatusManager` (`factorio_mod_manager/ui/status_manager.py`) runs a long-lived daemon thread that blocks on `status_queue.get(timeout=0.1)` in a `while self.running` loop. Each dequeued `(message, status_type)` tuple is dispatched to the main thread via:

```python
root.after_idle(lambda m=message, s=status_type: self.update_callback(m, s))
```

This is the only fully thread-safe UI update path in the application.

### Correct pattern — LoggerTab polling

`LoggerTab._poll_logs()` drains `log_queue` with `get_nowait()` inside a try/except, then reschedules itself:

```python
self.frame.after(100, self._poll_logs)
```

Because `after()` callbacks always execute on the Tk main thread, this is safe.

### Known bug — direct widget mutation from worker threads

Both `DownloaderTab` and `CheckerTab` spawn `threading.Thread` workers that call UI methods directly without going through `after()` or `after_idle()`. Real examples:

- `_run_download()` calls `self._update_mod_progress(mod_name, status)` which calls `.config()` on label widgets
- `_run_scan()` calls `self._update_mod_list()` which creates and packs Tkinter widgets

This is technically undefined behavior in Tkinter (Tk is not thread-safe) and will produce intermittent crashes or corrupted widget state under load. Any future rework must replace these direct calls with `root.after()` or `root.after_idle()` dispatches.

### Worker thread lifecycle

Worker threads are `threading.Thread` instances, not daemon threads by default. They are not explicitly joined — they self-terminate when their target function returns.

## Notification Architecture

`NotificationManager` is instantiated once in `MainWindow.__init__` and passed to both `DownloaderTab` and `CheckerTab` via `set_notification_manager()`. It overlays notifications on the **root window**, not inside any tab frame.

**Container placement:**

```python
self.container = tk.Frame(self.root, bg="#0e0e0e")
self.container.place(relx=0.5, y=70, anchor="n", width=700)
self.container.lift()
```

The container is centered horizontally, 70 px below the top of the root window (just below the blue accent separator), floated above all other content via `.lift()`. It is lazily created on first `show()` call and removed via `place_forget()` when the last notification is dismissed.

**`Notification` widget (`factorio_mod_manager/ui/widgets.py`):**
- Extends `tk.Frame`
- Type-to-color: `success` (#2d5016 bg / #4ec952 fg ✓), `error` (#3a0f0f / #d13438 ✗), `warning` (#3a2f1a / #ffad00 ⚠), `info` (#1a2a3a / #0078d4 ℹ)
- Auto-dismiss timer: `self.after(duration_ms, self.dismiss)` — cancelled on manual close or action click
- Persistent when `duration_ms=0` **or** when `actions` list is non-empty
- Action buttons call their callback then call `self.dismiss()`
- Notifications stack vertically inside the container; max 5 concurrent (oldest dismissed if exceeded)

**Calling convention:**

```python
# Transient (4 s auto-dismiss)
self._notify(message, notification_type="success", duration_ms=4000)

# Persistent with confirmation action
self._notify(message, notification_type="warning", duration_ms=0,
             actions=[("Confirm", callback)])
```

---

*Architecture analysis: 2026-04-10*
