---
plan: 04-01
phase: 04-queue-profiles
status: complete
commit: 6a2af10
---

# Plan 04-01 Summary: Core Data Contracts

## What was built

Three new core modules providing the typed contracts that all Phase 4 UI and worker plans build on:

### `factorio_mod_manager/core/mod_list.py` — `ModListStore`
- Reads `mod-list.json` enabled states keyed by mod name
- Atomic write via temp-file/replace — crash-safe
- Preserves unknown entries; enforces `base` always enabled
- `toggle()`, `enable()`, `disable()` convenience helpers

### `factorio_mod_manager/core/profiles.py` — Profile domain
- `Profile`: named desired-enabled-mod set (not ZIPs)
- `PresetSeed` + `CURATED_PRESETS`: Vanilla+, QoL, Logistics and Rail families
- `ProfileDiff` / `ProfileDiffItem`: immutable diff with add/remove/enable/disable/download actions
- `ProfileSnapshot`: pre-apply state for one-click undo
- `ProfileStore`: JSON persistence under `Config.CONFIG_DIR / "profiles"`
- `build_diff()`: deterministic diff builder

### `factorio_mod_manager/core/queue_models.py` — Queue operation contracts
- `OperationState`: queued / running / paused / completed / failed / canceled
- `QueueOperation`: typed immutable ID + mutable state, `continue_on_failure=True` default
- `QueueActionState`: computed legal action flags per state
- `QueueFailure`: plain-text failure details with retry eligibility
- `QueueResult`: outcome record

### `factorio_mod_manager/core/mod.py` — `Mod.enabled`
- Added `enabled: bool = True` field to represent mod-list.json state

## Test results
- 38 tests passing across `test_mod_list.py`, `test_profiles.py`, `test_queue_models.py`

## key-files
created:
  - factorio_mod_manager/core/mod_list.py
  - factorio_mod_manager/core/profiles.py
  - factorio_mod_manager/core/queue_models.py
  - tests/core/test_mod_list.py
  - tests/core/test_profiles.py
  - tests/core/test_queue_models.py
modified:
  - factorio_mod_manager/core/mod.py
  - factorio_mod_manager/core/__init__.py
