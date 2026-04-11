# Phase 2: Fluent Shell and UX System — Research

**Phase:** 02-fluent-shell-ux
**Date:** 2026-04-10
**Requirements:** UXUI-01, UXUI-02, UXUI-03

---

## RESEARCH COMPLETE

---

## 1. Standard Stack (confirmed from codebase audit)

| Concern | Library / Approach | Source |
|---------|-------------------|--------|
| Widgets | PySide6 built-ins — QMainWindow, QFrame, QSplitter, QStackedWidget, QListWidget, QTextEdit, QTableWidget, QProgressBar | existing imports |
| Styling | QSS (dark_theme.qss) + Python token constants (tokens.py) | existing codebase |
| Animation | QPropertyAnimation + QGraphicsOpacityEffect | already used in `Notification._start_fade()` |
| Threading | QThread + typed Signal/Slot | existing DownloadWorker, ScanWorker, etc. |
| Layout | QVBoxLayout / QHBoxLayout / QSplitter | existing codebase |
| Font | Segoe UI (main), system monospace (logs) | existing codebase |

No new packages required.

---

## 2. Architecture Patterns

### 2.1 Left Rail Navigation — Replace QTabWidget

**Current:** `MainWindow._create_tabs()` adds tabs to a `QTabWidget`.

**Pattern:** Replace with a `QFrame#navRail` (left, fixed width 200px) + `QStackedWidget` (right, stretch). Each rail item is a `QPushButton` with `checkable=True` and `autoExclusive` managed by a `QButtonGroup`.

```
QMainWindow
└── central QWidget
    └── QVBoxLayout (root)
        ├── QWidget#headerWidget        (existing _create_header — keep as-is)
        ├── QHBoxLayout (body)
        │   ├── QFrame#navRail          (new — fixed 200px wide)
        │   │   └── QVBoxLayout
        │   │       ├── QPushButton#navItem (Downloader, checkable)
        │   │       ├── QPushButton#navItem (Checker & Updates, checkable)
        │   │       ├── QPushButton#navItem (Logs, checkable)
        │   │       └── QSpacerItem (stretch)
        │   └── QStackedWidget#pageHost (new — replaces tab_widget body)
        │       ├── page 0: DownloaderPage (QWidget wrapping DownloaderTab scaffold)
        │       ├── page 1: CheckerPage
        │       └── page 2: LogsPage
        └── QStatusBar                  (existing, 28px)
```

**Key mechanics:**
- `QButtonGroup(exclusive=True)` tracks the active nav button.
- `button.toggled.connect(lambda checked, idx=i: page_host.setCurrentIndex(idx) if checked else None)`
- QSS active state: `QPushButton#navItem:checked { color: #0078d4; border-left: 3px solid #0078d4; }`
- No `QTabWidget` left in the shell after refactor.
- `self.tab_widget` reference → `self.page_host` throughout `MainWindow`.

**Existing bindings to preserve:**
- `self.downloader_tab`, `self.checker_tab`, `self.logger_tab` instance attributes — keep names the same; just change how they are inserted (into QStackedWidget instead of QTabWidget).
- `set_notification_manager()` calls in `_create_tabs()` — move into equivalent method.

### 2.2 Four-Zone Scaffold — Per-Page Widget Structure

Each page wraps its existing tab widget with this scaffold:

```
PageWidget (QWidget)
└── QVBoxLayout (page root, margin 0, spacing 0)
    ├── QWidget#pageHeader          (16px lr padding, computes to ~48px tall)
    │   └── QHBoxLayout
    │       ├── QLabel#pageTitle    (20pt 600 — from UI-SPEC)
    │       └── [primary CTA button if applicable]
    ├── QHBoxLayout (workspace row, stretch=1)
    │   ├── {page body} (stretch=1)
    │   └── QFrame#sidePanel (fixed 220px, collapsible)
    └── QFrame#feedbackRail         (fixed height per content)
```

**No existing page has this scaffold** — it must be built for all three pages. The safest refactor path is:
1. Keep each `*Tab` class's internal layout as-is (it becomes the "page body").
2. Wrap it in a new thin `*Page` QWidget that adds header + side panel + feedback rail.
3. `MainWindow` inserts the `*Page` wrapper into `QStackedWidget`, not the bare tab.

### 2.3 Downloader Two-Column Staged Flow

**Current state (downloader_tab.py audit):**
- Single `QVBoxLayout` root with: URL row → search results list → info panel → folder row → options row → download button → progress row (QHBoxLayout with left col + 220px sidebar).
- The "info panel" (mod info) is inline and hidden until resolve.
- Progress console is `QTextEdit` max 120px tall below the progress bar.
- Numerous inline `setStyleSheet()` calls (lines 185–222, 270–285) — violates QSS-only rule.

**Target two-column layout for Downloader page:**

```
DownloaderPage
└── QVBoxLayout (root, 0 margin)
    ├── QWidget#pageHeader
    │   └── "Downloader" heading + [Download Mods button — accent, disabled until step 3]
    ├── QSplitter (horizontal, stretch=1) ← replaces legacy VBox body
    │   ├── LEFT COLUMN (stretch=1): Input + stage panels
    │   │   ├── Stage 1 — Parse URL (always visible)
    │   │   │   ├── QLineEdit (URL/name field)
    │   │   │   ├── QListWidget (search dropdown, hidden by default)
    │   │   │   └── QPushButton "Load Mod" → triggers resolve → advances to Stage 2
    │   │   ├── Stage 2 — Mod Details + Dependencies (visible after resolve)
    │   │   │   ├── Mod title / author / summary card (QFrame#infoCard)
    │   │   │   ├── Dependencies section (required / optional — collapsible QFrame)
    │   │   │   └── QCheckBox "Include optional dependencies"
    │   │   ├── Stage 3 — Download Config (visible after Stage 2 confirmed)
    │   │   │   ├── Mods folder row (QLineEdit read-only + Browse button)
    │   │   │   └── [Download Mods] accent button (also mirrored in page header)
    │   │   └── Progress area (visible during/after download)
    │   │       ├── QProgressBar
    │   │       └── QTextEdit (console, expandable)
    │   └── RIGHT COLUMN (fixed 220px): Contextual side panel
    │       ├── "Selected Mod" header label
    │       ├── Per-mod status rows (existing `_add_sidebar_row` logic)
    │       └── Folder path summary
    └── QFrame#feedbackRail
```

**Staged visibility approach:** Use `QStackedWidget` or simple show/hide on stage panels. Prefer `show/hide` — simpler, no index tracking needed, and panels can overlap in layout without conflict.

**Inline `setStyleSheet()` calls to remove from `downloader_tab.py`:**
- `self.info_panel.setStyleSheet(...)` → replace with `self.info_panel.setObjectName("infoCard")` + QSS rule `QFrame#infoCard { ... }`
- `self.info_title_lbl.setStyleSheet(...)` → drop in favor of QSS on `QLabel#modTitle`
- `self.info_author_lbl.setStyleSheet(...)` → `QLabel#modAuthor`
- `self.info_meta_lbl.setStyleSheet(...)` → `QLabel#modMeta`
- `self.info_summary_lbl.setStyleSheet(...)` → `QLabel#modSummary`
- Dep label color inline styles → color responsibility moved to QSS `QLabel[depType="required"]`, etc.
- `_dep_divider.setStyleSheet(...)` → `QFrame#depDivider` in QSS
- `deps_hdr.setStyleSheet(...)` → `QLabel#depsHeader`

### 2.4 Checker Page Scaffold

**Current checker_tab.py** uses a `QSplitter` (horizontal) with left panel (controls) and right panel (table + log). This already approximates the workspace + side panel pattern.

**Minimal changes for scaffold compliance:**
1. Add `CheckerPage` wrapper with `#pageHeader` (title "Checker & Updates" + primary action button).
2. Promote existing `QSplitter` to "workspace + side panel" by assigning object names.
3. Wire feedback rail to existing `status_manager` signals.
4. Remove any remaining inline `setStyleSheet()` calls (audit needed per-file).

### 2.5 Logs Page Scaffold

**Current logger_tab.py** is extremely minimal (QTextEdit + toolbar). Easiest page to wrap.

**Changes:** Add `LogsPage` wrapper with `#pageHeader` (title "Logs" + "Clear Log" button migrated from internal toolbar).

---

## 3. QSS Extension Points

### New selectors to add to dark_theme.qss

```qss
/* ── Left Rail Navigation ─────────────────────────────────── */
QFrame#navRail {
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER_DEFAULT};
    min-width: 200px;
    max-width: 200px;
}

QPushButton#navItem {
    background-color: transparent;
    color: {FG_SECONDARY};
    border: none;
    border-left: 3px solid transparent;
    padding: 8px 16px;
    text-align: left;
    font-size: 10pt;
}

QPushButton#navItem:hover {
    background-color: {BTN_HOVER_BG};
    color: {FG_PRIMARY};
}

QPushButton#navItem:checked {
    background-color: {BG_PRIMARY};
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
    font-weight: 600;
}

/* ── Page Header Zone ─────────────────────────────────────── */
QWidget#pageHeader {
    background-color: {BG_PRIMARY};
    min-height: 48px;
    max-height: 48px;
}

QLabel#pageTitle {
    font-size: 20pt;
    font-weight: 600;
    color: {FG_PRIMARY};
    background: transparent;
}

/* ── Info Card (Downloader mod details) ───────────────────── */
QFrame#infoCard {
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
}

QLabel#modTitle {
    font-size: 14pt;
    font-weight: 600;
    color: {FG_PRIMARY};
    background: transparent;
    border: none;
}

QLabel#modAuthor {
    color: {FG_SECONDARY};
    font-size: 9pt;
    background: transparent;
    border: none;
}

QLabel#modMeta {
    color: {FG_DISABLED};
    font-size: 9pt;
    background: transparent;
    border: none;
}

QLabel#modSummary {
    color: {FG_PRIMARY};
    font-size: 10pt;
    background: transparent;
    border: none;
}

QFrame#depDivider {
    background: {BORDER_DEFAULT};
    border: none;
    max-height: 1px;
    min-height: 1px;
}

QLabel#depsHeader {
    font-size: 9pt;
    font-weight: 600;
    color: {FG_SECONDARY};
    background: transparent;
    border: none;
}

/* ── Side Panel ───────────────────────────────────────────── */
QFrame#sidePanel {
    background-color: {BG_PANEL};
    border-left: 1px solid {BORDER_DEFAULT};
    min-width: 220px;
    max-width: 220px;
}

/* ── Feedback Rail ────────────────────────────────────────── */
QFrame#feedbackRail {
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER_DEFAULT};
    min-height: 28px;
    max-height: 28px;
}
```

### Tokens to add to tokens.py

```python
# New tokens for Phase 2 Fluent shell
SPACING_2XL = 48      # Section breaks (UI-SPEC.md)
SPACING_3XL = 64      # Page-level rhythm (UI-SPEC.md)
NAV_RAIL_WIDTH = 200
SIDE_PANEL_WIDTH = 220
PAGE_HEADER_HEIGHT = 48
```

---

## 4. Motion and Animation Patterns

PySide6 already uses `QPropertyAnimation + QGraphicsOpacityEffect` in `Notification._start_fade()`. Same pattern applies to phase transitions and panel reveals.

### Panel reveal (120ms ease-out)

```python
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QGraphicsOpacityEffect

def _reveal_widget(widget: QWidget, duration_ms: int = 120) -> None:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)
    widget.setVisible(True)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    # Hold reference — Python GC will kill it otherwise
    widget._reveal_anim = anim
    anim.start()
```

**Note on Qt animation memory:** The animation object MUST be kept alive via `widget._reveal_anim = anim`. Qt does not prevent Python's GC from collecting it mid-run if only the local variable holds it.

### Section transition (160ms) — same pattern, different duration

### Focus ring (80ms linear)
- QSS `:focus` border change is instant by default in Qt.
- For animated focus ring, can use `QPropertyAnimation` on a custom `QFrame` overlay.
- **Recommendation:** Use CSS `:focus` in QSS only (instant, simpler, no overlay needed). Value: `border: 1px solid {BORDER_FOCUS}`. The timing value from UI-SPEC is aspirational — Qt does not support CSS transition on QSS border directly.

---

## 5. NotificationManager Enhancements (D-10, D-11)

### Current behavior (widgets.py)

- `show()` creates a `Notification`, appends to `self._active`, calls `reposition_all()`.
- Auto-dismiss via `QTimer.singleShot(duration_ms, self._start_fade)` in `Notification.__init__`.
- Duration is passed by caller — no severity-aware defaulting in `NotificationManager`.
- No deduplication/collapse logic.
- Cap at `_MAX_ACTIVE = 5` (DoS mitigation already present — T-03-02).

### Required changes

**A. Severity-aware duration defaults in `NotificationManager.show()`:**

```python
_SEVERITY_DURATIONS = {
    "success": 2800,
    "info":    2800,
    "warning": 4200,
    "error":   5600,
}
```

If caller passes `duration_ms=0` (or relies on default), `show()` resolves duration from `_SEVERITY_DURATIONS[notification_type]`.

**B. Event key deduplication (D-11):**

Add `event_key: Optional[str] = None` parameter to `show()`.
If `event_key` is not None and an active notification with the same key exists and was created within the last 2000ms:
- Update existing notification's message label text instead of spawning a new one.
- Reset its dismiss timer.
- Do NOT create a new `Notification` object.

Implementation: `self._keyed: dict[str, tuple[Notification, float]] = {}` — keyed by event key, value = (notification, created_timestamp).

**C. Caller-side changes:**
- All `_notify()` calls in `DownloaderTab` and `CheckerTab` that emit progress-style updates should pass `event_key="download_progress"` / `event_key="checker_scan"`.
- One-shot success/error messages do not need event keys.

---

## Validation Architecture

### Test approach

Phase 2 is pure UI refactor — no new business logic. Validation strategy:

1. **Smoke test:** App launches without `AttributeError` or missing widget references.
2. **Nav test:** Each nav rail item shows the correct page in `QStackedWidget`.
3. **Downloader flow test:** Starting from empty → load mod → mod info appears → download triggers worker.
4. **Toast deduplication test:** Two rapid `show()` calls with the same `event_key` produce one visible notification.
5. **Inline style audit:** `grep -rn "setStyleSheet" factorio_mod_manager/ui/ --include="*.py"` returns only `dark_theme.qss` application call and `Notification` icon inline style (or zero if moved to QSS).

All above verifiable with `python -c "from factorio_mod_manager.ui.main_window import MainWindow"` plus targeted unit checks.

---

## 7. Don't Hand-Roll

| Need | Use | Don't |
|------|-----|-------|
| Nav button group | `QButtonGroup(exclusive=True)` | Manual if/else across buttons |
| Page switching | `QStackedWidget.setCurrentIndex()` | Show/hide individual pages |
| Animation | `QPropertyAnimation` + `QEasingCurve` | Manual QTimer step-based animation |
| Style tokens | `tokens.py` constants in Python + `.format(**tokens)` | Hard-coded hex values per widget |
| Scroll areas | `QScrollArea(widgetResizable=True)` | Manually sized inner widgets |

---

## 8. Common Pitfalls

1. **QPropertyAnimation GC:** Always store animation reference on the widget (`widget._anim = anim`), not just local scope.
2. **QSS specificity thrash:** `QFrame#navRail QPushButton#navItem:checked` beats `QPushButton#navItem:checked` — be consistent with selector depth in dark_theme.qss.
3. **QStackedWidget resize policy:** Each page widget needs `setSizePolicy(Expanding, Expanding)` or the stacked widget will shrink to the smallest page.
4. **inline setStyleSheet + QSS conflict:** If any remnant `setStyleSheet()` call remains on a widget, it overrides ALL QSS rules for that widget. Must zero them all out.
5. **QSplitter minimum sizes:** Set `setChildrenCollapsible(False)` and `setStretchFactor` to prevent side panel from collapsing on resize.
6. **Thread safety for notification collapse:** `NotificationManager._keyed` dict is only accessed from the main thread (Qt signal/slot ensures this) — no mutex required.

---

## 9. Implementation Order (recommended for planner)

| Wave | Work | Files |
|------|------|-------|
| 1 | Tokens + QSS extensions (style contracts first, zero risk) | tokens.py, dark_theme.qss |
| 1 | NotificationManager severity durations + event_key dedup | widgets.py |
| 2 | MainWindow shell refactor (QTabWidget → left rail + QStackedWidget) | main_window.py |
| 2 | Downloader page scaffold + inline style purge + staged flow | downloader_tab.py |
| 3 | Checker page scaffold + inline style purge | checker_tab.py |
| 3 | Logs page scaffold | logger_tab.py |
| 4 | Smoke test + grep audit (inline styles = 0) | — |

Wave 1 is fully independent. Wave 2 depends on Wave 1 (tokens/QSS must exist before widgets reference new selectors). Wave 3 depends on Wave 2 shell (pages reference `QStackedWidget` host). Wave 4 is verification.

---

## 10. Requirement Mapping

| Requirement | D-XX decisions | Research findings |
|------------|----------------|-------------------|
| UXUI-01 — Consistent Fluent visual system | D-01, D-02, D-03, D-04 | §3 QSS extensions, tokens additions, inline style purge |
| UXUI-02 — Consistent navigation hierarchy | D-05, D-06, D-07, D-08 | §2.1 left rail, §2.2 four-zone scaffold, §2.3 downloader layout |
| UXUI-03 — Non-blocking immediate feedback | D-09, D-10, D-11, D-12 | §5 NotificationManager enhancements |
