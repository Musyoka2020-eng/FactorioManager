"""Thread-safe status manager — QObject signal-based (replaces daemon thread)."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QStatusBar


class StatusManager(QObject):
    """Receives status updates from any thread and forwards to QStatusBar on main thread.

    Usage:
        manager = StatusManager(self.statusBar())
        # From any thread (worker QThread):
        manager.push_status("Downloading...", "info")
    """

    _status_signal: Signal = Signal(str)

    def __init__(self, status_bar: QStatusBar) -> None:
        super().__init__()
        self._status_bar = status_bar
        # AutoConnection: if emitter is on a different thread, the slot is queued
        # onto the main thread's event loop automatically.
        self._status_signal.connect(self._status_bar.showMessage)

    def push_status(self, message: str, status_type: str = "info") -> None:
        """Emit status update. Thread-safe — can be called from QThread.run()."""
        self._status_signal.emit(message)

    def clear(self) -> None:
        """Clear status bar text."""
        self._status_signal.emit("")

