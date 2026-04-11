# 04-03 SUMMARY — Move Downloader onto shared queue

**Phase:** 04-queue-profiles  
**Plan:** 03  
**Commit:** 42a8c05  
**Wave:** 3  
**Tests:** 63 total (11 new in `tests/ui/test_download_queue_job.py`)

## What was built

### `factorio_mod_manager/core/downloader.py` (modified)
- Added `import threading`
- Added `_cancel_event: threading.Event` and `_pause_event: threading.Event` in `__init__`
- Added `set_cancel_event()` and `set_pause_event()` so `DownloadQueueJob` injects its events before the thread starts
- Added cooperative pause/cancel checks inside `_download_with_re146` chunk loop:
  - Spins in `time.sleep(0.05)` while `_pause_event` is set
  - Immediately breaks on `_cancel_event`, cleans up partial zip, returns `False`

### `factorio_mod_manager/ui/download_queue_job.py` (new)
- `_DownloadThread(QThread)` — private worker; accepts `cancel_event` and `pause_event` events; honours early cancel in `run()`; emits `progress(int, int)` and `finished(bool, list)`
- `DownloadQueueJob(QObject)` — public job class
  - `start(controller)` — creates `_DownloadThread`, wires signals, subscribes to `controller.queue_changed` for reactive pause/resume/cancel
  - `pause()` / `resume()` / `cancel()` — direct event manipulation
  - `_on_queue_changed()` — mirrors operation state → cooperative event flags (drawer-driven pause/cancel)
  - `_on_finished()` — routes success to `controller.complete()`; failure to `controller.fail()` with `QueueFailure(retriable=True)`; cancel is silently ignored (controller already owns state)
  - Inspect payload populated on failure: `mod_url`, `mods_folder`, `include_optional`, `failed_mods`
  - Retry metadata exposed as properties: `mod_url`, `mods_folder`, `include_optional`

### `factorio_mod_manager/ui/downloader_tab.py` (modified)
- Imports: added `QueueOperation`, `OperationKind`, `OperationSource`, `OperationState`, `DownloadQueueJob`, `QueueStrip`
- Added `_queue_controller = None` and `_active_jobs = {}` to `__init__`
- Added `set_queue_controller(controller)` injection method (called by `MainWindow`)
- Inserted `QueueStrip(source_filter=OperationSource.DOWNLOADER)` into the right panel between `Download Mods` button and `_progress_widget`; wired `open_queue_requested` → `main_win.open_queue_drawer()`
- `_on_download()` rewired:
  - When `_queue_controller` is present: creates `QueueOperation` + `DownloadQueueJob`, enqueues, calls `start_next()`, then `job.start(controller)`. Keeps legacy progress console visible for inline feedback.
  - Falls back to the original `DownloadWorker` path when no controller is wired (safe default)
- Added `_on_queue_progress(ops, op_id)` — mirrors controller `queue_changed` into progress bar and toasts for the active download operation

## Key decisions (from CONTEXT.md)
| Decision | Implemented |
|----------|-------------|
| D-04 continue-on-failure | `QueueOperation(continue_on_failure=True)` default |
| D-03 global badge | queue_controller.enqueue() triggers badge update |
| Inline strip placement | Between Download button and progress console per UI-SPEC |

## Threats mitigated
| ID | Mitigation |
|----|-----------|
| T-04-07 | URL/mod-name normalised before enqueueing; inspect payload is plain-text only |
| T-04-08 | `_worker.isRunning()` guard in `start()` prevents duplicate workers |
| T-04-09 | Failure detail stored as plain str, never rendered as HTML |
