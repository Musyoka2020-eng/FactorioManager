"""Reusable compact queue summary strip.

Rendered inside Downloader and Checker pages to surface queue state
without requiring the user to open the global drawer.  All labels use
plain-text Qt widgets — no rich text or HTML.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.queue_models import OperationSource, OperationState, QueueOperation


class QueueStrip(QFrame):
    """Compact single-line strip showing active queue summary for a workflow page.

    Emits :attr:`open_queue_requested` when the user clicks "Open Queue".
    """

    open_queue_requested = Signal()

    def __init__(self, source_filter: Optional[OperationSource] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueStrip")
        self._source_filter = source_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._summary_label = QLabel("No active queue items")
        self._summary_label.setObjectName("stripSummary")
        layout.addWidget(self._summary_label)

        layout.addStretch()

        self._open_btn = QPushButton("Open Queue")
        self._open_btn.setObjectName("stripOpenButton")
        self._open_btn.setAccessibleName("Open Queue drawer")
        self._open_btn.setAccessibleDescription(
            "Opens the global queue drawer showing all active operations"
        )
        self._open_btn.setFlat(True)
        self._open_btn.clicked.connect(self.open_queue_requested)
        layout.addWidget(self._open_btn)

        self.setVisible(False)  # hidden until there are relevant items

    def update_from_operations(self, operations: List[QueueOperation]) -> None:
        """Update strip text and visibility from the current operations list."""
        relevant = [
            op for op in operations
            if self._source_filter is None or op.source == self._source_filter
        ]
        active = [
            op for op in relevant
            if op.state in (
                OperationState.QUEUED,
                OperationState.RUNNING,
                OperationState.PAUSED,
                OperationState.FAILED,
            )
        ]

        if not active:
            self.setVisible(False)
            return

        running = sum(1 for op in active if op.state == OperationState.RUNNING)
        queued = sum(1 for op in active if op.state == OperationState.QUEUED)
        paused = sum(1 for op in active if op.state == OperationState.PAUSED)
        failed = sum(1 for op in active if op.state == OperationState.FAILED)

        parts = []
        if running:
            parts.append(f"{running} running")
        if queued:
            parts.append(f"{queued} queued")
        if paused:
            parts.append(f"{paused} paused")
        if failed:
            parts.append(f"{failed} failed")

        self._summary_label.setText(", ".join(parts))
        self.setVisible(True)
