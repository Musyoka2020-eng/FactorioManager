---
plan: 04-02
phase: 04-queue-profiles
status: complete
commit: 49689a2
---

# Plan 04-02 Summary: Queue Controller and Shell Surfaces

## What was built

### `factorio_mod_manager/ui/queue_controller.py` — `QueueController`
- `QObject` owning ordered `QueueOperation` list
- Signals: `queue_changed`, `badge_count_changed`, `drawer_open_requested`, `inspect_requested`
- Legal transition enforcement: pause/resume/cancel/retry/skip with correct state guards
- Reorder: only QUEUED items move; RUNNING pinned per plan spec
- Badge counts: QUEUED + RUNNING + PAUSED + FAILED; excludes COMPLETED/CANCELED
- `continue_on_failure=True` default per D-04; 50-item terminal retention limit

### `factorio_mod_manager/ui/queue_drawer.py` — `QueueDrawer`
- Non-modal right-edge `QFrame` anchored to `MainWindow` central widget
- `toggle()` / `open_drawer()` / `hide_drawer()` API
- Renders cards in order: running → paused → queued → failed → completed/canceled
- Per-card action buttons derived from `operation.action_state` (state-specific)
- Clear Completed button; repositions on parent resize

### `factorio_mod_manager/ui/queue_strip.py` — `QueueStrip`
- Compact single-line strip for inline page embedding
- Source-filtered (shows only ops from the relevant workflow)
- Hidden when no active items; `open_queue_requested` signal for shell drawer

### `factorio_mod_manager/ui/main_window.py`
- Inserted queue badge `QPushButton#queueBadge` between global search and settings per D-03
- `queue_controller: QueueController` shared instance exposed to child pages
- `open_queue_drawer()` helper: opens drawer without navigating away from current page
- Badge property `active` set for QSS dynamic styling

### Theme files
- Phase 4 QSS selectors for: queueBadge, queueDrawer, queueCard, queueStrip,
  state chips (chipQueued/Running/Paused/Completed/Failed/Canceled), diffPreviewPanel
- Phase 4 tokens in `tokens.py`: drawer width, badge size, card/chip radius, semantic colors

## Test results
- 14 queue controller tests passing
