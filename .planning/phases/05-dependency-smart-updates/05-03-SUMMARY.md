# Plan 05-03 Summary — Checker Intelligence Layer

## Commit
`2b6135d` — feat(05-03): add ClassifyWorker pipeline, SmartUpdateStrip, Guidance column, guidance filter, and fix _on_view_details

## What was built

### checker_logic.py
- Added import: `from ..core.update_guidance import UpdateGuidanceClassifier, GuidanceResult, UpdateClassification`
- Added `classify_updates(mods: dict) -> dict[str, GuidanceResult]` method — runs classifier for every mod, logs each result, returns REVIEW fallback on exception

### checker_tab.py
- Added import: `from ..core.update_guidance import UpdateClassification, GuidanceResult`
- Added `QDialog` to PySide6 imports
- Added 3 new classes before CheckerTab:
  - **`ClassifyWorker(QThread)`** — background thread, emits `guidance_ready: Signal(object)`
  - **`SmartUpdateStrip(QWidget)`** — full-width strip with Safe/Review/Risky count chips + "Queue Safe Updates" button (accent, disabled until Safe > 0)
  - **`_UpdateConfirmDialog(QDialog)`** — confirmation dialog showing counts for Review/Risky selections; returns 2 for "View Details"
- Added instance vars to `__init__`: `_guidance: dict`, `_guidance_filter: str`, `_classify_worker`
- Changed `setColumnCount(7 → 8)` with new "Guidance" column at index 4 (Version→5, Author→6, Downloads→7)
- Added "Guidance chip" in `_populate_table` col 4 (Safe=#4ec952, Review=#ffad00, Risky=#d13438)
- Updated `_on_enabled_changed` dim loop to cover cols 2-7
- Added SmartUpdateStrip wiring in `_setup_ui` after queue strip
- Added Selected Update Guidance group box to right sidebar (before `addStretch`)
- Added guidance filter combo wiring in `_setup_ui`
- Added `_start_classify()` calls in `_on_mods_loaded` and `_on_check_complete`
- Fixed `_on_update_selected` to show `_UpdateConfirmDialog` before queuing Review/Risky items
- Replaced `_on_view_details` (was: toast notification) → now opens `ModDetailsDialog`
- Added new methods: `_on_view_details_from_guidance`, `_start_classify`, `_on_guidance_ready`, `_update_smart_strip`, `_update_guidance_panel`, `_on_queue_safe_updates`, `_on_guidance_filter_changed`
- Updated `_on_checkbox_changed` to call `_update_smart_strip()` and `_update_guidance_panel()`

### filter_sort_bar.py
- Added `guidance_changed = Signal(str)` after `filter_changed`
- Added `add_guidance_combo()` method with `_GUIDANCE_OPTIONS` list
- Added `_on_guidance_changed` handler

### checker_presenter.py
- Added `guidance_chip_info(classification) -> tuple[str, str]` staticmethod

## Verification
- All 4 modules import cleanly
- `setColumnCount(8)` confirmed
- `guidance_changed = Signal(str)` confirmed in filter_sort_bar.py
- `class ClassifyWorker`, `SmartUpdateStrip`, `_UpdateConfirmDialog` all present
- `_on_view_details` opens ModDetailsDialog (no more toast)
- Test suite: **92 passed, 0 failed** (no regressions)

## Files modified
- `factorio_mod_manager/ui/checker_tab.py` — +371 lines
- `factorio_mod_manager/ui/checker_logic.py` — +25 lines
- `factorio_mod_manager/ui/checker_presenter.py` — +14 lines
- `factorio_mod_manager/ui/filter_sort_bar.py` — +23 lines
