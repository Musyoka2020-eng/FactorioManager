# Phase 1 Research: Qt Platform Migration and Behavior Parity

**Phase:** 01 — Qt Platform Migration and Behavior Parity
**Researched:** 2026-04-10
**Status:** Complete

---

## Summary

Replace the 6-file Tkinter `ui/` layer with PySide6 equivalents. All core logic (`core/`, `utils/`) is framework-agnostic and untouched. The migration maps each Tkinter threading pattern to a `QThread` worker with signals/slots, replaces `root.after()` timers with `QTimer`, and delivers a global QSS stylesheet (`dark_theme.qss`) driven by a `tokens.py` constants module.

---

## Standard Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| GUI framework | PySide6 (6.x) | Locked in D-06; LGPL license; first-party Qt bindings |
| Styling | QSS global stylesheet (`dark_theme.qss`) | D-09; Phase 2 Fluent expansion requires extractable file |
| Threading | `QThread` subclass + `Signal`/`Slot` | D-06/D-07; Qt-native, event loop safe, no `after_idle()` |
| Log bridge | Custom `logging.Handler` → `Signal` via `QObject` bridge | D-08; cleanest pattern for `QueueHandler` → Qt |
| Animation | `QGraphicsOpacityEffect` + `QPropertyAnimation` | Only safe opacity animation for embedded child widgets |
| Debounce | `QTimer.setSingleShot(True)` | Replaces `root.after()` cancel/reschedule pattern |

---

## Architecture Patterns

### 1. QThread Worker Pattern (canonical PySide6)

All three operations (`DownloadWorker`, `ScanWorker`, `UpdateCheckWorker`) use the same subclass pattern:

```python
from PySide6.QtCore import QThread, Signal

class DownloadWorker(QThread):
    progress = Signal(int, int)       # (completed, total)
    mod_status = Signal(str, str)     # (mod_name, status_text)
    log_message = Signal(str, str)    # (message, level_name)
    finished = Signal(bool, list)     # (success, failed_list)

    def __init__(self, url: str, mods_folder: str, ...):
        super().__init__()
        self._url = url
        self._mods_folder = mods_folder

    def run(self) -> None:
        # Runs in worker thread — emit signals to update UI
        self.log_message.emit("Starting download...", "INFO")
        self.progress.emit(1, 5)
        ...
        self.finished.emit(True, [])
```

Connection in UI:
```python
self._worker = DownloadWorker(url, folder)
self._worker.progress.connect(self._on_progress)
self._worker.log_message.connect(self._on_log)
self._worker.finished.connect(self._on_finished)
self._worker.start()
```

**Critical:** `QThread` instances must be kept alive (store as `self._worker`). Local variables will be garbage-collected mid-operation.

### 2. StatusManager Qt Pattern (replaces daemon thread)

Old `StatusManager` uses a daemon thread + `root.after_idle()`. New pattern uses a `QObject` signal — PySide6 cross-thread signal emission is safe (queues to main thread automatically when connection type is `AutoConnection`):

```python
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QStatusBar

class StatusManager(QObject):
    _status_signal = Signal(str)

    def __init__(self, status_bar: QStatusBar):
        super().__init__()
        self._status_bar = status_bar
        self._status_signal.connect(self._status_bar.showMessage)

    def push_status(self, message: str, status_type: str = "info") -> None:
        """Thread-safe: can be called from any thread."""
        self._status_signal.emit(message)
```

No polling thread needed — PySide6 `AutoConnection` automatically routes cross-thread `emit()` calls through the event loop.

### 3. Logger Bridge (D-08)

The existing `QueueHandler` wraps a Python `Queue`. For Qt, replace with a `QObject` bridge that holds a `Signal`. `setup_logger()` in `utils/logger.py` gains a `qt_bridge` parameter:

```python
class LogSignalBridge(QObject):
    """Bridges Python logging system to Qt signal system."""
    log_record = Signal(str, str)  # (formatted_message, level_name)

class QtLoggingHandler(logging.Handler):
    def __init__(self, bridge: LogSignalBridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bridge.log_record.emit(self.format(record), record.levelname)
        except Exception:
            self.handleError(record)
```

`LoggerTab` creates a `LogSignalBridge`, connects `bridge.log_record` to its `_append_log` slot, and passes the bridge to `setup_logger()`. This eliminates `_poll_logs()` and the 100 ms `after()` timer entirely.

### 4. QSS Loading Pattern (D-09)

Two files in `factorio_mod_manager/ui/styles/`:

**`tokens.py`** — module-level string constants:
```python
BG_PRIMARY = "#0e0e0e"
BG_PANEL = "#1a1a1a"
ACCENT = "#0078d4"
# ... all tokens from UI-SPEC.md Color Tokens section
```

**`dark_theme.qss`** — parameterized template using Python `str.format_map()` placeholders:
```qss
QMainWindow, QWidget { background-color: {BG_PRIMARY}; color: {FG_PRIMARY}; }
QPushButton { background-color: {BG_PANEL}; color: {FG_PRIMARY}; border: 1px solid #3a3a3a; }
QPushButton:hover { border: 1px solid {ACCENT}; background-color: #2a2a2a; }
QPushButton#accentButton { background-color: {ACCENT}; color: #ffffff; border: none; }
/* ... full stylesheet ... */
```

**Loader** (in `styles/__init__.py` or `utils`):
```python
from pathlib import Path
from . import tokens

def load_stylesheet() -> str:
    qss_path = Path(__file__).parent / "dark_theme.qss"
    template = qss_path.read_text(encoding="utf-8")
    token_map = {k: v for k, v in vars(tokens).items() if not k.startswith("_")}
    return template.format_map(token_map)
```

Applied once at startup: `QApplication.instance().setStyleSheet(load_stylesheet())`

### 5. Notification Overlay (D-12)

`Notification` and `NotificationManager` are embedded `QFrame` child widgets of the `QMainWindow.centralWidget()`. They are NOT standalone windows.

**Critical — opacity animation on embedded widgets requires `QGraphicsOpacityEffect`:**
```python
from PySide6.QtCore import QPropertyAnimation, QAbstractAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect

class Notification(QFrame):
    dismissed = Signal()

    def __init__(self, parent: QWidget, message: str, notif_type: str = "info",
                 duration_ms: int = 4000, actions: list | None = None):
        super().__init__(parent)
        # Set dynamic property for QSS selector: QFrame[notifType="success"]
        self.setProperty("notifType", notif_type)
        self.setFixedWidth(420)
        ...
        self._build_layout(message, notif_type, actions)
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self._start_fade)

    def _start_fade(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.dismissed.emit)
        anim.finished.connect(self.deleteLater)
        anim.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)
```

`NotificationManager` positions toasts via `move()` (absolute positioning within `centralWidget()`). Reposition on `MainWindow.resizeEvent()`:
```python
def reposition_all(self, container_rect: QRect) -> None:
    x_right = container_rect.right() - 16
    y = container_rect.top() + 16 + HEADER_HEIGHT
    for notif in self._active:
        notif.move(x_right - notif.width(), y)
        y += notif.height() + 8
```

### 6. Debounced URL Search (replaces `root.after` cancel/restart)

```python
self._search_timer = QTimer(self)
self._search_timer.setSingleShot(True)
self._search_timer.setInterval(500)  # 500 ms — matches PARITY-CHECKLIST.md
self._search_timer.timeout.connect(self._perform_search)

def _on_url_changed(self, text: str) -> None:
    self._search_timer.stop()   # Cancel any pending search
    if text.strip():
        self._search_timer.start()  # Restart 500 ms countdown
```

### 7. Auto-Scan on First CheckerTab Show (replaces `<Visibility>` binding)

```python
class CheckerTab(QWidget):
    def __init__(self, parent=None, ...):
        super().__init__(parent)
        self._first_show = True

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(3000, self._start_auto_scan)
```

**Critical:** Must guard against duplicate fires. `_first_show = True` flag set in `__init__`, cleared the first time `showEvent` fires.

### 8. Color-Coded Log Lines in QTextEdit

```python
LEVEL_COLORS = {
    "INFO": "#0078d4",
    "DEBUG": "#b0b0b0",
    "WARNING": "#ffad00",
    "ERROR": "#d13438",
    "CRITICAL": "#d13438",
    "SUCCESS": "#4ec952",
}

def _append_log(self, message: str, level_name: str) -> None:
    color = LEVEL_COLORS.get(level_name, "#e0e0e0")
    html = f'<span style="color:{color};">{message}</span>'
    cursor = self.log_text.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertHtml(html + "<br>")
    # Auto-scroll
    sb = self.log_text.verticalScrollBar()
    sb.setValue(sb.maximum())
```

### 9. QTableWidget for Checker Mod List

```python
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox

table = QTableWidget(0, 6)  # rows=0 initially, 6 columns
table.setHorizontalHeaderLabels(["", "Name", "Status", "Version", "Author", "Downloads"])
table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
table.setColumnWidth(0, 30)  # checkbox column
table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
table.setAlternatingRowColors(False)  # Handled by QSS alternating-row rules
table.setSortingEnabled(False)  # Manual sort via right sidebar radio buttons
```

Row insertion:
```python
row = table.rowCount()
table.insertRow(row)
chk = QCheckBox()
table.setCellWidget(row, 0, chk)
table.setItem(row, 1, QTableWidgetItem(mod.name))
status_item = QTableWidgetItem(status_icon)
status_item.setForeground(QColor(status_color))
table.setItem(row, 2, status_item)
```

---

## Don't Hand-Roll

| Don't build | Use instead |
|-------------|------------|
| Cross-thread UI update queue + polling thread | PySide6 `Signal` with `AutoConnection` (automatic) |
| Custom fade animation from scratch | `QGraphicsOpacityEffect` + `QPropertyAnimation` |
| Manual DPI awareness via `ctypes.windll` | Qt6 handles DPI automatically; `ctypes` DPI call in `main.py` can remain as belt-and-suspenders but is no longer required |
| Parsing QSS in Python | `str.format_map(token_dict)` on the `.qss` template |
| Custom scroll-to-bottom implementation | `scrollBar().setValue(scrollBar().maximum())` |

---

## Common Pitfalls

| Pitfall | Impact | Mitigation |
|---------|--------|-----------|
| `QThread.run()` accessing `self` attributes set after `start()` | Data race / crash | Set all worker attributes in `__init__()` before `start()` |
| Using `QWidget.setWindowOpacity()` on embedded (non-toplevel) widgets | Silent no-op | Use `QGraphicsOpacityEffect` for embedded `QFrame` toasts |
| Calling UI widgets directly from `QThread.run()` | Crashes / undefined behavior | Only emit signals from `run()`; never call widget methods directly |
| `QThread` garbage-collected mid-run | Abort crash | Store worker as `self._worker` on the parent widget |
| Inline `setStyleSheet()` calls on individual widgets | Overrides global QSS; breaks Phase 2 Fluent override path | All styling in `dark_theme.qss`; use object names for per-widget rules |
| Forgetting `QTimer.stop()` before `.start()` restart in debounce | Multiple concurrent timers | Always `.stop()` first, then `.start()` |
| Using `QPyObject` auto-delete of signal bridge before `LoggerTab` connects | Lost log messages | Hold `LogSignalBridge` on `MainWindow` (not `LoggerTab`) for lifetime control |
| `setProperty()` QSS dynamic properties not updating visually | QSS selector not re-evaluated | Call `self.style().unpolish(w); self.style().polish(w)` after dynamic property change |
| Auto-scan firing on every tab switch after first show | Duplicate scans | Guard with `_first_show` bool; check running status before scheduling |

---

## Module Plan (per D-03)

| Plan | Files Modified | Content |
|------|---------------|---------|
| 01 | `pyproject.toml`, `requirements.txt`, `ui/styles/tokens.py`, `ui/styles/dark_theme.qss`, `ui/styles/__init__.py`, `main.py` | Foundation: deps, style system, QApplication entry point |
| 02 | `ui/main_window.py`, `ui/status_manager.py` | QMainWindow + QTabWidget shell; Qt StatusManager |
| 03 | `ui/widgets.py` | Notification, NotificationManager (QFrame overlay + fade) |
| 04 | `ui/logger_tab.py`, `utils/logger.py` | LoggerTab QTextEdit + LogSignalBridge handler |
| 05 | `ui/downloader_tab.py` | DownloadWorker QThread, URL field, debounce, progress sidebar |
| 06 | `ui/checker_tab.py` | ScanWorker/UpdateCheckWorker, QTableWidget, three-column layout |

All plans are independent vertical slices after Plan 01+02 are complete. Plans 03–06 depend on Plans 01+02 (styles + main window scaffolded). Plans 03, 04, 05, 06 are parallel in Wave 2.

---

## Validation Architecture

```yaml
validation_strategy:
  approach: "manual behavioral verification against PARITY-CHECKLIST.md"
  automated_checks:
    - command: "python -c \"import factorio_mod_manager.ui; print('Qt import OK')\""
      verifies: "PySide6 available and ui module importable"
    - command: "python -m py_compile factorio_mod_manager/ui/main_window.py factorio_mod_manager/ui/downloader_tab.py factorio_mod_manager/ui/checker_tab.py factorio_mod_manager/ui/logger_tab.py factorio_mod_manager/ui/widgets.py factorio_mod_manager/ui/status_manager.py"
      verifies: "All Qt UI files compile without syntax errors"
    - command: "grep -r 'import tkinter\\|from tkinter\\|ttk\\.' factorio_mod_manager/ui/ && echo FAIL_tkinter_found || echo PASS_no_tkinter"
      verifies: "No Tkinter imports remain in ui/ module"
    - command: "python -c \"from factorio_mod_manager.main import main; print('Entry point OK')\""
      verifies: "main.py uses QApplication (importable without GUI display)"
  manual_verification:
    - "Launch app: window opens maximized, minimum 1100x750 enforced"
    - "Three tabs visible with correct labels and emoji"
    - "No Tkinter windows or console errors at startup"
    - "Downloader: URL debounce fires ~500ms after typing stops"
    - "Downloader: Download operation updates progress bar and sidebar rows"
    - "Checker: Auto-scan fires ~3s after first tab switch"
    - "Checker: QTableWidget rows with checkboxes, status icons"
    - "Logs: Color-coded entries appear from both tabs"
    - "Notifications: Toast appears top-right, auto-dismisses with fade"
    - "Dark theme: all colors match UI-SPEC.md token table"
    - "No legacy Tkinter imports reachable via any production code path"
  parity_checklist: ".planning/phases/00-pre-migration-cleanup/PARITY-CHECKLIST.md"
  parity_items_total: 125
```

---

## RESEARCH COMPLETE

**Phase:** 01 — Qt Platform Migration and Behavior Parity
**Key finding:** 6 vertical slice plans (foundation → main window → widgets → logger → downloader → checker). Plans 03–06 are parallel in Wave 2. PySide6 signals handle all cross-thread Qt safety automatically — no polling threads. The single hardest migration is the notification overlay opacity animation (requires `QGraphicsOpacityEffect`, not `setWindowOpacity`).
