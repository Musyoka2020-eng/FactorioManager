"""Logger tab — Qt implementation. Signal-driven; no polling timer."""
from __future__ import annotations

import html as html_lib
from queue import Queue
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFontDatabase

if TYPE_CHECKING:
    from factorio_mod_manager.utils.logger import LogSignalBridge

# Log level → hex color (D-10 + UI-SPEC.md Log Line Color Contract)
_LEVEL_COLORS: dict[str, str] = {
    "INFO": "#0078d4",
    "DEBUG": "#b0b0b0",
    "WARNING": "#ffad00",
    "ERROR": "#d13438",
    "CRITICAL": "#d13438",
    "SUCCESS": "#4ec952",
}
_DEFAULT_COLOR = "#e0e0e0"


class LoggerTab(QWidget):
    """Logs tab — real-time signal-driven log display."""

    def __init__(
        self,
        log_queue: Optional[Queue] = None,
        log_bridge: Optional["LogSignalBridge"] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._log_queue = log_queue  # kept for API compat; not polled
        self._setup_ui()
        if log_bridge is not None:
            # Direct signal connection — thread-safe via AutoConnection
            log_bridge.log_record.connect(self._append_log)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        page_title = QLabel("Logs")
        page_title.setObjectName("pageTitle")
        header_layout.addWidget(page_title)
        header_layout.addStretch()
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_logs)
        header_layout.addWidget(clear_btn)
        root.addWidget(header)

        # Log display — monospace, read-only, color-coded via insertHtml
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSize(10)
        self.log_text.setFont(mono_font)
        root.addWidget(self.log_text, stretch=1)

    @Slot(str, str)
    def _append_log(self, message: str, level_name: str) -> None:
        """Append a color-coded log entry. Called on main thread via Signal."""
        color = _LEVEL_COLORS.get(level_name.upper(), _DEFAULT_COLOR)
        # Escape HTML entities in the message to prevent injection via log content
        safe_message = html_lib.escape(message)
        html_line = f'<span style="color:{color};">{safe_message}</span>'
        self.log_text.append(html_line)
        # Auto-scroll to latest entry
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self) -> None:
        """Clear all log entries from the display (PREP-04 behavior)."""
        self.log_text.clear()
