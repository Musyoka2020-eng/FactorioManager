# Codebase Concerns

**Analysis Date:** 2026-04-10

## Tech Debt

**Monolithic UI tab classes mix presentation, orchestration, and domain behavior:**
- Issue: Very large modules handle widget rendering, threading, API calls, parsing, and state mutation in one place.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Impact: High change risk, difficult debugging, and frequent regressions when adding features.
- Fix approach: Split into smaller units (view, controller/presenter, worker/service), and keep UI thread code separate from background operations.

**Business rules duplicated across layers:**
- Issue: Dependency parsing and dependency-related display behavior are implemented in both core API logic and UI logic.
- Files: `factorio_mod_manager/core/portal.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Impact: Drift between behavior in download path vs display path, harder maintenance.
- Fix approach: Move dependency parsing and formatting into a single core module and call it from UI.

**Error handling strategy is inconsistent and frequently broad:**
- Issue: Widespread bare `except:` and `except Exception` blocks throughout UI and helpers.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`, `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/status_manager.py`, `factorio_mod_manager/utils/helpers.py`
- Impact: Real defects are masked, logs are incomplete, and behavior can fail silently.
- Fix approach: Catch specific exceptions, log structured context, and fail fast for non-recoverable states.

**`selenium` declared as a dependency but excluded from the build and never imported:**
- Issue: `pyproject.toml` lists `selenium = "^4.25.0"` as a runtime dependency, but `FactorioModManager.spec` explicitly excludes it (`excludes=['selenium', 'playwright', 'greenlet']`), and no source file imports it.
- Files: `pyproject.toml`, `FactorioModManager.spec`
- Impact: Unnecessary heavyweight transitive dependency (WebDriver binaries); potential confusion for contributors about intended functionality.
- Fix approach: Remove `selenium` from `pyproject.toml` dependencies entirely.

## Known Bugs

**Tkinter widgets are updated directly from worker threads:**
- Symptoms: Intermittent UI instability, racey rendering, and potential `TclError` crashes under load.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Trigger: `_scan_thread` (line ~1156) calls `_populate_mods_list()` and `_update_stats()` directly on the background thread; `_check_thread` (line ~1209) and update/backup threads (lines ~1279, ~1345) do the same; `_search_thread` and `_load_dependencies_thread` in `downloader_tab.py` call `_display_mod_info()` directly; the changelog fetch thread in `checker_tab.py` (line ~1724) creates `tk.Label` widgets from a background thread. None of these go through `after()` or `after_idle()`.
- Workaround: Route all widget-mutating calls through `self.frame.after(0, callback)` or `after_idle(callback)` so Tcl/Tk processes them on the main thread.

**Download button can remain permanently disabled when offline check fails:**
- Symptoms: After a failed offline check, `download_btn` stays greyed out; the user cannot retry without restarting the app or navigating away and back.
- Files: `factorio_mod_manager/ui/downloader_tab.py` — `_start_download()` method (lines ~772–792)
- Trigger: `download_btn.config(state="disabled")` and `self.is_downloading = True` are set unconditionally at line ~772. The subsequent offline check at line ~789 returns early without re-enabling the button. The finalizer path that re-enables (`self.download_btn.config(state="normal")`, line ~893) is only reached if the background thread was actually started, which it is not when offline.
- Workaround: Re-enable the button before each early-return guard, or wrap the entire button-disable/re-enable life-cycle in `try/finally`.

## Dead Code

**Authenticated `requests.Session` and stored credentials are never used for any actual request:**
- What it is: `Config.DEFAULTS` stores `"username": None` and `"token": None` in `~/.factorio_mod_manager/config.json`. Both are passed into `ModDownloader.__init__` (`factorio_mod_manager/core/downloader.py`, lines ~35–40) and `FactorioPortalAPI.__init__` (`factorio_mod_manager/core/portal.py`, lines ~39–46), where an authenticated `requests.Session` is constructed with `self.session.auth = (username, token)` when credentials are present.
- Why it is dead: `ModDownloader._download_with_re146()` (line ~227) downloads via a plain module-level `requests.get(mirror_url, ...)` call, **not** `self.session.get()`. All `FactorioPortalAPI` metadata calls (`get_mod`, `get_mod_dependencies`, changelog fetch) use `self.session.get()` against public, unauthenticated endpoints (`https://mods.factorio.com/api/mods/...`) that return data without any auth. The session auth headers are constructed but never exercised by any real HTTP request.
- Impact: No functionality is lost by removing auth entirely. The credential storage UI that doesn't exist yet (see Missing Features) would need a real auth path before credentials have any purpose.
- Fix approach: Remove `self.session.auth` setup from both `ModDownloader.__init__` and `FactorioPortalAPI.__init__`. Optionally remove credential fields from `Config.DEFAULTS` until an authenticated download path is actually implemented. This simplifies both classes and eliminates a misleading code path.

**`LoggerTab.clear_logs()` method exists but is not reachable from any UI element:**
- What it is: `clear_logs()` method defined in `factorio_mod_manager/ui/logger_tab.py` (line ~79).
- Why it is dead: No button, menu item, or keyboard shortcut in the UI calls it. There is no Settings tab or toolbar to expose it.
- Fix approach: Add a "Clear" button to the logger tab toolbar, or expose it in a planned Settings/UI controls panel.

## Missing Features (Not in UI)

**Theme toggle — only dark mode is functional:**
- `Config.DEFAULTS` includes `"theme": "dark"` (`factorio_mod_manager/utils/config.py`), but no light/system theme is implemented and no toggle exists in the UI.

**Settings tab / preferences panel:**
- Config keys `theme`, `auto_backup`, `auto_refresh`, `max_workers`, `username`, and `token` are all defined in `factorio_mod_manager/utils/config.py`, but there is no Settings tab or preferences dialog to view or edit them. Users have no way to change these values through the app.

**Clear log button:**
- `LoggerTab.clear_logs()` exists in `factorio_mod_manager/ui/logger_tab.py` but is not exposed in the UI (see Dead Code above).

**Mod search / browse from portal:**
- The downloader accepts direct URL or mod name input only. There is no portal browse/search interface to discover mods by category, keyword, or tag.

**Automatic app updates:**
- No self-update mechanism or update check on launch. Referenced conceptually but absent from codebase.

**Mod enable/disable toggle:**
- Factorio supports disabling mods via `mod-list.json`. No enable/disable toggle exists in either the checker or downloader tab.

**Per-mod changelog in Details popup:**
- The checker tab has a changelog fetch thread code path (`checker_tab.py`, line ~1724), but the fetched content is not rendered in a visible per-mod details panel accessible to the user.

## Security Considerations

**Credentials stored in plaintext config file:**
- Risk: Factorio token can be read from local disk by other processes or users with filesystem access.
- Files: `factorio_mod_manager/utils/config.py` — `Config.save()` writes plain JSON to `~/.factorio_mod_manager/config.json`.
- Current mitigation: None. No file permission hardening, encryption, or OS keychain integration.
- Recommendations: Use OS keyring/credential manager (`keyring` library) for tokens; store only non-sensitive settings in the JSON file. Note: credentials are currently dead code (see Dead Code section), so this is a forward-looking concern if an authenticated download path is ever activated.

**Downloads sourced from external third-party mirror without cryptographic integrity verification:**
- Risk: Supply-chain tampering or unexpected artifact substitution is harder to detect; the mirror (`https://mods-storage.re146.dev`) is not the official Factorio portal.
- Files: `factorio_mod_manager/core/downloader.py` — `_download_with_re146()` (line ~227) calls plain `requests.get(mirror_url, ...)`.
- Current mitigation: ZIP structural validation only (`zipfile.testzip`), which does not verify provenance or content authenticity.
- Recommendations: Prefer official authenticated download URLs returned by `FactorioPortalAPI.get_mod_download_url`; compare checksums from portal release metadata against downloaded files; add provenance logging.

**Broad exception swallowing can hide security-relevant failures:**
- Risk: Auth/network/proxy/certificate failures can be downgraded into generic silent UI behavior.
- Files: `factorio_mod_manager/ui/status_manager.py` (bare `except:` in queue processor), `factorio_mod_manager/ui/logger_tab.py` (bare `except:` in `_poll_logs`), `factorio_mod_manager/ui/downloader_tab.py` (multiple bare catches in widget/scroll handlers).
- Current mitigation: Partial ad-hoc logging in some paths.
- Recommendations: Replace bare catches with specific exception types; log structured context including exception type and message; fail fast for non-recoverable states.

## Performance Bottlenecks

**Aggressive polling loops in UI status and log pipelines:**
- Problem: Recurring `after(100, ...)` wakeups fire at 10 Hz regardless of whether there is new work.
- Files: `factorio_mod_manager/ui/logger_tab.py` — `_poll_logs()` (line ~76); `factorio_mod_manager/ui/status_manager.py` — `process_queue()` background thread polling with `timeout=0.1`.
- Cause: Fixed 100ms interval regardless of queue depth or idle state.
- Improvement path: Use event-driven wakeup (`queue.get()` with blocking + `after_idle` post) instead of constant polling; coalesce batches of log entries per tick.

**Dependency resolution can re-fetch the same portal metadata on every traversal:**
- Problem: Excess API calls when downloading multiple mods with overlapping dependency trees.
- Files: `factorio_mod_manager/core/downloader.py` — `resolve_dependencies()` (line ~105); `factorio_mod_manager/core/portal.py` — `get_mod()`.
- Cause: `resolve_dependencies` uses a `visited` set to avoid re-traversal within one call, but a new `visited` set is created per top-level resolution call, so shared transitive dependencies are fetched fresh for each root mod in a batch.
- Improvement path: Add a request-level cache (e.g., `functools.lru_cache` or a shared dict keyed by `(mod_name, version)`) that persists across the lifetime of a download session.

**Full mod list rebuild on every filter change:**
- Problem: Filtering the checker mod list destroys and recreates all row widgets for every keypress.
- Files: `factorio_mod_manager/ui/checker_tab.py` — `_populate_mods_list()` (line ~688) and the filter path (line ~954).
- Cause: No incremental update strategy; entire widget tree is torn down and rebuilt.
- Improvement path: Implement show/hide toggling on existing rows, or use a virtual list that only renders the visible viewport.

## Fragile Areas

**Shared mutable state modified across threads without synchronization guarantees:**
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Why fragile: Collections like `self.mods`, `self.selected_mods`, `self.mod_widgets`, and `self.is_downloading` are read and written by both worker threads and UI event handlers with no locks or atomic transitions.
- Safe modification: Isolate all mutable state updates to the main thread; pass only immutable data (copies, named tuples) from worker threads through the `after()` queue.
- Test coverage: No automated concurrency tests exist.

**Logging and status pipelines suppress errors silently:**
- Files: `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/status_manager.py`
- Why fragile: Bare `except:` blocks in `_poll_logs` and the status queue processor swallow all exceptions, including widget destruction errors, making failures invisible and leaving the UI in stale states.
- Safe modification: Catch specific exception types; add explicit exception logging with `logger.exception()`; implement self-healing restart for processors where needed.
- Test coverage: No tests for queue processors or UI log rendering behavior.

**Changelog fetch thread creates Tkinter widgets from a background thread:**
- Files: `factorio_mod_manager/ui/checker_tab.py` (line ~1724 `fetch_changelog_thread`)
- Why fragile: Creating `tk.Label` and other widgets outside the main thread violates Tkinter's single-thread rule and can produce non-deterministic `TclError` crashes that are hard to reproduce.
- Safe modification: Pass fetched data back to main thread via `after()` callback and construct all widgets there.
- Test coverage: None.

## Scaling Limits

**Network/API concurrency and UI responsiveness are tightly coupled to fixed worker counts:**
- Current capacity: Hardcoded `max_workers=4` in `Config.DEFAULTS` (`factorio_mod_manager/utils/config.py`) and `ModDownloader.__init__`; no way to change this from the UI.
- Limit: Throughput and responsiveness degrade with large mod collections and slow portal responses.
- Scaling path: Expose `max_workers` in a Settings panel; apply adaptive backpressure for large dependency graphs.

**Single-process Tkinter architecture limits high-volume interactive operations:**
- Current capacity: Suitable for moderate mod counts (tens to low hundreds).
- Limit: Heavy background activity and frequent widget-level UI updates increase main-thread contention and Tcl/Tk event loop saturation.
- Scaling path: Coalesce UI updates per scheduler tick; reduce cross-thread communication frequency; batch widget operations.

## Dependencies at Risk

**Dependency declaration drift between `pyproject.toml` and `requirements.txt`:**
- Risk: `selenium` is declared in `pyproject.toml` but absent from `requirements.txt` and never imported by any source file. Other version pins may also diverge silently.
- Impact: Environment inconsistency across install methods; avoidable build/runtime surprises for contributors.
- Migration plan: Choose one canonical dependency source; auto-generate the other with CI enforcement. Remove `selenium` from `pyproject.toml` (it is never used and already excluded in the PyInstaller spec).

**No lockfile committed for reproducible dependency resolution:**
- Risk: Transitive dependency changes may silently alter behavior between installs.
- Impact: Non-deterministic installs and harder regression triage.
- Migration plan: Commit `poetry.lock` (or a pip-compiled `requirements.lock`) and enforce it in CI.

## Test Coverage

**Zero automated tests exist in the repository:**
- State: `pytest = "^7.4.0"` is declared as a dev dependency in `pyproject.toml`, but no `tests/` directory, `test_*.py`, or `*_test.py` files are present anywhere in the workspace.
- Affected areas: All core logic (`factorio_mod_manager/core/`), all UI state transitions (`factorio_mod_manager/ui/`), all utility functions (`factorio_mod_manager/utils/`).
- Risk: Every release depends exclusively on manual validation. Confirmed bugs (thread-safety violations, permanently disabled download button) cannot be caught by CI. Refactoring any of the large UI tab classes carries high regression risk with no safety net.
- Priority: High — minimum viable coverage should start with pure-function unit tests for `factorio_mod_manager/utils/helpers.py`, portal response parsing in `factorio_mod_manager/core/portal.py`, `Config` load/save in `factorio_mod_manager/utils/config.py`, and the `Mod` data model in `factorio_mod_manager/core/mod.py` before any structural refactoring is attempted.

---

*Concerns audit: 2026-04-10*
