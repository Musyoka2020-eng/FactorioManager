# Plan 04-05 — SUMMARY

**Phase:** 04-queue-profiles  
**Plan:** 05  
**Commit:** `70dccdd`  
**Tests:** 77 total (7 new in `tests/core/test_profile_apply.py`)

## What Was Built

### `factorio_mod_manager/ui/profile_apply_job.py` (NEW)
- `_ApplyThread(QThread)`: background worker that (a) captures `enabled_before` snapshot, (b) persists it via `ProfileStore.save_snapshot()` before any mutation, (c) applies ENABLE/DISABLE changes via `ModListStore`, (d) emits `apply_done(snapshot_id, [dl_mods])`.
- `ProfileApplyJob(QObject)`: queue-owned executor wrapping one `QueueOperation`.
  - `start(controller)` — idempotent guard (`_worker.isRunning()` check, T-04-08).
  - `_on_apply_done` — enqueues linked `DownloadQueueJob` operations (one per DOWNLOAD diff item) then calls `controller.complete()` with `QueueResult(snapshot_id=..., linked_operation_ids=[...])`.
  - `_on_apply_failed` — calls `controller.fail()` with `retriable=True`.

### `factorio_mod_manager/ui/profile_apply_dialog.py` (NEW)
- `ProfileApplyDialog(QDialog)`: two-pane confirmation dialog (≥900 px).
  - Left rail (240 px fixed): profile title, 3 count chips (Enable / Disable / Download), filter radio buttons (All / Downloads only / Local only), Confirm Apply + Cancel.
  - Right pane: `QListWidget#diffList` with colour-coded entries per `DiffAction`.
  - No signals — caller reads `dialog.exec()` result.

### `factorio_mod_manager/ui/checker_tab.py` (MODIFIED)
- **New imports**: `ModListStore`, `ProfileStore`, `CURATED_PRESETS`, `build_diff`.
- **`__init__`**: Added `_current_apply_op_id: Optional[str]` and `_profile_store = ProfileStore()`.
- **`set_queue_controller()`**: Sets `controller._undo_callback = self._on_undo_restore_callback` so `QueueDrawer._on_undo()` duck-typing propagates to the checker tab.
- **`_on_profile_selected()`**: Full implementation — resolves profile by name (saved) or by `PresetFamily.value` (curated presets), computes diff via `build_diff()`, opens `ProfileApplyDialog`, invalidates previous undo, enqueues `ProfileApplyJob`.
- **`_on_apply_queue_progress()`**: Reacts to COMPLETED (shows 10 s toast with "Undo Restore" action + triggers re-scan) / FAILED (error toast).
- **`_trigger_undo()`**: Forwards toast action → `_on_undo_restore_callback`.
- **`_on_undo_restore_callback(operation_id)`**: Full undo restore — loads snapshot, writes `ModListStore` entries, calls `invalidate_snapshot` + `invalidate_undo`, triggers re-scan.

### QSS (MODIFIED)
- `dark_theme.qss` + `light_theme.qss`: Added `#applyDialogRail`, `#applyProfileTitle`, `#applyProfileSub`, `#applyDialogRight`, `#diffList`, `#diffListLabel`, `#applyDialogDivider` selectors.

## Verification

- `python -m compileall factorio_mod_manager/ui -q` → clean
- `python -c "from factorio_mod_manager.ui.checker_tab import CheckerTab; ..."` → IMPORT_OK
- `python -m pytest -q` → **77 passed**

## Decisions Honoured

| ID | Decision | Status |
|----|----------|--------|
| D-13 | Pre-apply snapshot for undo restore | ✅ Full |
| D-14 | Undo token invalidated on new apply | ✅ Full (T-04-14 guard) |
| D-15 | No ZIP deletion on disable | ✅ `ModListStore.disable()` only touches mod-list.json |
| D-04 | continue_on_failure for linked downloads | ✅ set on linked operations |

## Key Links

- `_ApplyThread.run()` → `ProfileStore.save_snapshot()` → `ModListStore.enable/disable()` → `apply_done`
- `ProfileApplyJob._on_apply_done` → `DownloadQueueJob` per DOWNLOAD item → `controller.complete(snapshot_id=...)`
- `QueueDrawer._on_undo(op_id)` → `controller._undo_callback(op_id)` → `CheckerTab._on_undo_restore_callback()`
- `CheckerTab._on_profile_selected(name)` → `build_diff()` → `ProfileApplyDialog` → `ProfileApplyJob.start(controller)`
