# Plan 01-02 Summary: QMainWindow + Signal StatusManager

## Status: COMPLETE

## What Was Built
- Rewrote `factorio_mod_manager/ui/status_manager.py`: `StatusManager(QObject)` with `Signal`; `push_status()` thread-safe via PySide6 AutoConnection; no daemon thread
- Rewrote `factorio_mod_manager/ui/main_window.py`: `MainWindow(QMainWindow)` with `showMaximized()`, `setMinimumSize(1100, 750)`, header (title + `QFrame#headerSeparator`), `QTabWidget` (3 tabs), fixed-height status bar, `StatusManager(self.statusBar())`; deferred imports with fallback placeholders for tabs not yet implemented; `resizeEvent()` calls `notification_manager.reposition_all()`

## Key Decisions
- Deferred tab imports (try/except ImportError → QLabel placeholder) for safe incremental migration
- `log_bridge` parameter added to `MainWindow.__init__` (passed through to `LoggerTab` in Plan 04)
- `run()` method removed — `QApplication.exec()` handles the event loop in `main.py`

## Key Files Modified
- `factorio_mod_manager/ui/status_manager.py` (rewritten)
- `factorio_mod_manager/ui/main_window.py` (rewritten)

## Deviations
- None

## Verification Results
- `python -m py_compile factorio_mod_manager/ui/main_window.py factorio_mod_manager/ui/status_manager.py` → PASS
- `from factorio_mod_manager.ui.main_window import MainWindow` → PASS
- No tkinter imports → PASS
