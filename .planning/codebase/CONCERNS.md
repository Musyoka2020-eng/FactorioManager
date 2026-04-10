# Codebase Concerns

**Analysis Date:** 2026-04-09

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
- Issue: Widespread `except:` and `except Exception` blocks in UI and helpers.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`, `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/status_manager.py`, `factorio_mod_manager/utils/helpers.py`
- Impact: Real defects are masked, logs are incomplete, and behavior can fail silently.
- Fix approach: Catch specific exceptions, log structured context, and fail fast for non-recoverable states.

## Known Bugs

**Tkinter widgets are updated from worker threads:**
- Symptoms: Intermittent UI instability, racey rendering, and potential `TclError` crashes under load.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Trigger: Background thread methods call widget-mutating methods directly (`_scan_thread` calling `_populate_mods_list` and `_update_stats`; `_search_thread` and `_load_dependencies_thread` calling `_display_mod_info`; changelog fetch thread creating labels).
- Workaround: Route all widget updates through `after()`/`after_idle()` to main thread only.

**Download button can remain disabled when offline check fails:**
- Symptoms: User cannot retry download until app/tab state is manually reset.
- Files: `factorio_mod_manager/ui/downloader_tab.py`
- Trigger: `_start_download` disables `download_btn`, then returns early on offline state before reaching thread/finalizer path.
- Workaround: Re-enable the button before each early return or wrap state transitions in `try/finally` on caller side.

## Security Considerations

**Credentials are stored in plaintext config file:**
- Risk: Factorio token can be read from local disk by other processes/users with access.
- Files: `factorio_mod_manager/utils/config.py`
- Current mitigation: None detected (plain JSON write to `~/.factorio_mod_manager/config.json`).
- Recommendations: Use OS keyring/credential manager for tokens; keep config file for non-secret settings only.

**Downloads are sourced from an external mirror without cryptographic integrity verification:**
- Risk: Supply-chain tampering or unexpected artifact substitution is harder to detect.
- Files: `factorio_mod_manager/core/downloader.py`
- Current mitigation: ZIP structural validation only (`zipfile.testzip`), which does not verify provenance.
- Recommendations: Prefer official authenticated source where possible, verify checksums/signatures from trusted metadata, and add retry/backoff with provenance logging.

**Broad exception swallowing can hide security-relevant failures:**
- Risk: Auth/network/proxy/certificate failures can be downgraded into generic UI behavior.
- Files: `factorio_mod_manager/ui/status_manager.py`, `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Current mitigation: Partial ad-hoc logging.
- Recommendations: Replace bare catches with specific exceptions and explicit failure telemetry.

## Performance Bottlenecks

**Aggressive polling loops in UI status/log pipelines:**
- Problem: Frequent polling loop wakeups even when idle.
- Files: `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/status_manager.py`
- Cause: `while True` drain loop with 100ms recurring `after`, plus queue polling thread with `timeout=0.1`.
- Improvement path: Use event-driven wakeups where possible, increase intervals when idle, and avoid broad exception loops.

**Dependency resolution can re-fetch the same metadata repeatedly:**
- Problem: Excess API calls for multi-root downloads with overlapping dependency trees.
- Files: `factorio_mod_manager/core/downloader.py`
- Cause: `resolve_dependencies` memoization is scoped per traversal; repeated root mods can trigger duplicate portal fetches.
- Improvement path: Add request-level and batch-level cache keyed by mod name/version.

**Large UI modules build many widgets synchronously:**
- Problem: Rendering and refresh can become slow with large mod sets.
- Files: `factorio_mod_manager/ui/checker_tab.py`
- Cause: Full list rebuild patterns and heavy per-row widget creation.
- Improvement path: Incremental updates, virtualization, or batched render scheduling.

## Fragile Areas

**Shared mutable state modified across threads without synchronization guarantees:**
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`
- Why fragile: Collections like `self.mods`, selection state, and UI status are touched by worker and UI paths.
- Safe modification: Isolate mutable state updates to main thread and communicate via immutable queue messages.
- Test coverage: No automated concurrency tests detected.

**Logging and status pipelines suppress errors silently:**
- Files: `factorio_mod_manager/ui/logger_tab.py`, `factorio_mod_manager/ui/status_manager.py`
- Why fragile: Bare `except` makes failures invisible and can leave UI in stale state.
- Safe modification: Instrument with explicit exception logging and self-healing restart for processors.
- Test coverage: No tests detected for queue processors or UI log rendering behavior.

## Scaling Limits

**Network/API concurrency and UI responsiveness are tightly coupled to fixed worker counts:**
- Current capacity: Hardcoded small pools (`max_workers=4` patterns in core operations).
- Limit: Throughput and responsiveness degrade with large mod collections and slow portal responses.
- Scaling path: Configurable concurrency per operation plus adaptive backpressure.

**Single-process Tkinter architecture limits high-volume interactive operations:**
- Current capacity: Suitable for moderate mod counts.
- Limit: Heavy background activity and frequent UI updates increase contention and responsiveness issues.
- Scaling path: Coalesce UI updates, reduce cross-thread chatter, and isolate long tasks into clearer worker channels.

## Dependencies at Risk

**Dependency declaration drift between manifests:**
- Risk: `pyproject.toml` and `requirements.txt` are not aligned (example: `selenium` declared in poetry metadata but absent from requirements and not referenced in source imports).
- Impact: Environment inconsistency across install methods; avoidable build/runtime surprises.
- Migration plan: Choose one canonical dependency source or auto-generate one from the other with CI checks.

**No lockfile committed for reproducible dependency resolution:**
- Risk: Transitive dependency changes may alter behavior over time.
- Impact: Non-deterministic installs and harder regression triage.
- Migration plan: Commit lockfile for selected package manager and enforce in CI.

## Missing Critical Features

**Network resilience policies are incomplete:**
- Problem: No standardized retry/backoff/circuit-breaking policy for portal and mirror calls.
- Blocks: Reliable behavior under intermittent network conditions and better user trust during failures.

**Artifact trust verification is incomplete:**
- Problem: Download validation checks structure but not trusted source integrity.
- Blocks: Strong assurance for downloaded mod artifacts.

## Test Coverage Gaps

**Core update/download/check flows are untested:**
- What's not tested: Dependency resolution edge cases, backup/restore/update flows, and portal error-type handling.
- Files: `factorio_mod_manager/core/downloader.py`, `factorio_mod_manager/core/checker.py`, `factorio_mod_manager/core/portal.py`
- Risk: Behavior regressions in high-impact flows can ship unnoticed.
- Priority: High

**UI threading and state-transition logic is untested:**
- What's not tested: Button state transitions, background-thread UI update safety, and notification sequencing.
- Files: `factorio_mod_manager/ui/checker_tab.py`, `factorio_mod_manager/ui/downloader_tab.py`, `factorio_mod_manager/ui/status_manager.py`, `factorio_mod_manager/ui/logger_tab.py`
- Risk: Intermittent bugs and dead controls are difficult to reproduce and fix.
- Priority: High

**Automated test suite not detected in repository:**
- What's not tested: End-to-end workflows and regression checks across releases.
- Files: `pyproject.toml` (test dependency present), workspace test file search (`**/*.{test,spec}.py`) found none.
- Risk: Every release depends primarily on manual validation.
- Priority: High

---

*Concerns audit: 2026-04-09*
