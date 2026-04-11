# 04-04 SUMMARY — Checker enabled-state, update queue jobs, and profile library

**Phase:** 04-queue-profiles  
**Plan:** 04  
**Commit:** 4cfd023  
**Wave:** 3  
**Tests:** 70 total (7 new in `tests/core/test_checker_mod_state.py`)

## What was built

### `factorio_mod_manager/core/checker.py` (modified)
- Added `from .mod_list import ModListStore` import
- `scan_mods()` now merges `ModListStore.load()` enabled flags into every `Mod.enabled` field after the portal pass; mods absent from `mod-list.json` default to `enabled=True` (Factorio default)

### `factorio_mod_manager/ui/checker_logic.py` (modified)
- Added `enable_mod(mod_name)` — calls `ModListStore.enable()`, updates in-memory `checker.mods[name].enabled = True`
- Added `disable_mod(mod_name)` — calls `ModListStore.disable()`, updates in-memory state; ZIP is never deleted (D-15)

### `factorio_mod_manager/ui/checker_tab.py` (modified)
- Added `_queue_controller = None` and `_active_jobs: dict = {}` to `__init__`
- Added `set_queue_controller(controller)` injection method (wires `queue_changed` → strip update)
- Added "Profiles" button to header → opens `ProfileLibraryDialog`
- Table column count `6 → 7`: col 0 = bulk-select (unchanged), col 1 = "On" enabled toggle (new), cols 2–6 shifted
- `_populate_table`: adds enabled `QCheckBox` at col 1, dims cols 2–6 (`#888888`) for disabled mods
- Added `_on_enabled_changed()` — calls `enable_mod`/`disable_mod` and updates row dim state in-place without table rebuild
- Added `QueueStrip(source_filter=CHECKER)` between filter bar and splitter; wired `open_queue_requested` → `main_win.open_queue_drawer()`
- `_on_update_selected` / `_on_update_all` rewired: when controller present, enqueues `UpdateQueueJob` instead of page-local worker; legacy `UpdateSelectedWorker` path retained as fallback
- Added `_on_update_queue_progress()` mirrors queue state → toasts + table refresh
- Added `_on_open_profiles()` / `_on_profile_selected()` profile entry point

### `factorio_mod_manager/ui/update_queue_job.py` (new)
- `_UpdateThread(QThread)`: runs `checker_logic.update_mods(mod_names)`, honours early cancel
- `UpdateQueueJob(QObject)`: wraps one `QueueOperation` for an update batch, cooperative cancel via `_cancel_event`, mirrors drawer cancel via `queue_changed`, failure exposed with `retriable=True`

### `factorio_mod_manager/ui/profile_library_dialog.py` (new)
- `ProfileLibraryDialog(QDialog)` with three sections in a scrollable layout
  - Save Current as Profile: `QLineEdit` + Save button → `ProfileStore.save()` from `ModListStore` enabled state
  - Saved Profiles: `QListWidget` + Apply/Delete buttons → `ProfileStore.load_all()` / `delete()`
  - Starter Presets: `CURATED_PRESETS` cards (Vanilla+, QoL, Logistics and Rail) with per-card Apply
- `profile_selected(str)` signal emits profile name or preset family value to caller

### Theme files (modified)
- `dark_theme.qss` + `light_theme.qss`: Added `#profileLibraryCard`, `#sectionHeader`, `#sectionDescription`, `#presetFamilyName`, `#presetFamilyDesc` selectors

## Key decisions honoured
| Decision | Status |
|----------|--------|
| D-14 separate enabled toggle | Dedicated "On" column at col 1, separate from bulk-select at col 0 |
| D-15 disable keeps ZIP | `disable_mod()` writes mod-list.json only, no file removal |
| D-07 profile = desired enabled set | `Profile.from_enabled_state()` used in Save Current |
| PROF-05 3 preset families | Vanilla+, QoL, Logistics and Rail cards rendered |

## Threats mitigated
| ID | Mitigation |
|----|-----------|
| T-04-10 | All toggles route through `ModListStore` atomic writes |
| T-04-11 | Profile names and labels rendered as plain-text Qt labels only |
| T-04-12 | `UpdateQueueJob` start() is idempotent; duplicates prevented by `isRunning()` guard |
