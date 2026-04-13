"""Global queue drawer — non-modal right-edge panel.

Anchored below the shell header; opened/closed by the header queue badge.
Renders the summary strip, active queue list, failed items, and recently
completed items.  All labels use plain-text Qt widgets — no rich text.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dataclasses import replace

from ..core.queue_models import OperationState, QueueOperation
from .queue_strip import QueueStrip

logger = logging.getLogger(__name__)

_STATE_CHIP_MAP = {
    OperationState.QUEUED: ("Queued", "chipQueued"),
    OperationState.RUNNING: ("Running", "chipRunning"),
    OperationState.PAUSED: ("Paused", "chipPaused"),
    OperationState.COMPLETED: ("Done", "chipCompleted"),
    OperationState.FAILED: ("Failed", "chipFailed"),
    OperationState.CANCELED: ("Canceled", "chipCanceled"),
}


class _QueueItemCard(QFrame):
    """Single queue operation card displayed in the drawer."""

    def __init__(
        self,
        operation: QueueOperation,
        on_pause: Callable,
        on_resume: Callable,
        on_cancel: Callable,
        on_retry: Callable,
        on_skip: Callable,
        on_inspect: Callable,
        on_undo: Callable,
        on_move_up: Callable,
        on_move_down: Callable,
        action_state_override=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("queueCard")
        self._op = operation

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Row 1: label + source chip + state chip
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        label = QLabel(operation.label or operation.kind.value)
        label.setObjectName("cardLabel")
        row1.addWidget(label, stretch=1)

        src_chip = QLabel(operation.source.value)
        src_chip.setObjectName("chipQueued")  # reuse queued style for source label
        row1.addWidget(src_chip)

        chip_text, chip_name = _STATE_CHIP_MAP.get(operation.state, ("?", "chipQueued"))
        state_chip = QLabel(chip_text)
        state_chip.setObjectName(chip_name)
        row1.addWidget(state_chip)
        layout.addLayout(row1)

        # Progress bar for running items (thin, 4 px)
        if operation.state == OperationState.RUNNING:
            prog_bar = QProgressBar()
            prog_bar.setObjectName("cardProgressBar")
            prog_bar.setRange(0, 100)
            prog_bar.setValue(operation.progress if operation.progress is not None else 0)
            prog_bar.setTextVisible(False)
            layout.addWidget(prog_bar)

        # Failure description for failed items
        if operation.state == OperationState.FAILED and operation.failure:
            fail_label = QLabel(operation.failure.short_description)
            fail_label.setObjectName("cardError")
            fail_label.setWordWrap(True)
            layout.addWidget(fail_label)

        # Row 2: action buttons
        actions = action_state_override if action_state_override is not None else operation.action_state
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addStretch()

        op_id = operation.id

        def _btn(text: str, cb: Callable, accessible: str) -> QPushButton:
            b = QPushButton(text)
            b.setFlat(True)
            b.setObjectName("cardActionBtn")
            b.setAccessibleName(accessible)
            b.clicked.connect(lambda: cb(op_id))
            row2.addWidget(b)
            return b

        if actions.can_move_up:
            _btn("↑", on_move_up, "Move up")
        if actions.can_move_down:
            _btn("↓", on_move_down, "Move down")
        if actions.can_pause:
            _btn("Pause", on_pause, "Pause this operation")
        if actions.can_resume:
            _btn("Resume", on_resume, "Resume this operation")
        if actions.can_retry:
            _btn("Retry Failed Item", on_retry, "Retry this failed operation")
        if actions.can_skip:
            _btn("Skip Failed Item", on_skip, "Skip this failed operation")
        if actions.can_inspect:
            _btn("Inspect Details", on_inspect, "Inspect operation details")
        if actions.can_cancel:
            _btn("Cancel", on_cancel, "Cancel this operation")
        if actions.can_undo:
            _btn("Undo Restore", on_undo, "Undo the last profile apply")

        if row2.count() > 1:  # >1 means at least one action button
            layout.addLayout(row2)


class QueueDrawer(QFrame):
    """Non-modal right-edge queue drawer managed by :class:`QueueController`.

    Call :meth:`toggle()` to show/hide.  The drawer must be parented to MainWindow
    so it overlays the page host from the right edge.

    Signals
    -------
    close_requested
        Emitted when the user clicks the close button inside the drawer.
    """

    close_requested = Signal()

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueDrawer")
        self._controller = controller
        self._visible_state = False

        from .styles.tokens import QUEUE_DRAWER_WIDTH
        self.setFixedWidth(QUEUE_DRAWER_WIDTH)
        self.setVisible(False)

        self._build_ui()
        controller.queue_changed.connect(self._on_queue_changed)

        # Install event filter on the top-level window so _reposition tracks resizes
        top = self.window()
        if top is not None and top is not self:
            top.installEventFilter(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def toggle(self) -> None:
        """Toggle drawer visibility."""
        if self._visible_state:
            self.hide_drawer()
        else:
            self.open_drawer()

    def open_drawer(self) -> None:
        """Show the drawer and refresh content."""
        self._refresh()
        self._visible_state = True
        self.setVisible(True)
        self._reposition()

    def hide_drawer(self) -> None:
        """Hide the drawer."""
        self._visible_state = False
        self.setVisible(False)

    # ------------------------------------------------------------------
    # Internal build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row
        header = QWidget()
        header.setObjectName("drawerHeader")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(12, 8, 8, 8)
        hrow.setSpacing(8)

        title = QLabel("Queue")
        title.setObjectName("drawerTitle")
        hrow.addWidget(title, stretch=1)

        clear_btn = QPushButton("Clear Done")
        clear_btn.setObjectName("cardActionBtn")
        clear_btn.setFlat(True)
        clear_btn.setAccessibleName("Clear completed and canceled queue items")
        clear_btn.clicked.connect(self._on_clear_completed)
        hrow.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("cardActionBtn")
        close_btn.setFlat(True)
        close_btn.setFixedSize(28, 28)
        close_btn.setAccessibleName("Close queue drawer")
        close_btn.clicked.connect(self.hide_drawer)
        hrow.addWidget(close_btn)

        layout.addWidget(header)

        # Summary strip at top of drawer
        self._summary_strip = QueueStrip(source_filter=None, parent=self)
        self._summary_strip.open_queue_requested.connect(lambda: None)  # already in drawer
        layout.addWidget(self._summary_strip)

        # Scroll area for item list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("drawerScroll")

        self._list_widget = QWidget()
        self._list_widget.setObjectName("drawerList")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, stretch=1)

    def _on_queue_changed(self, operations: list) -> None:
        if self._visible_state:
            self._refresh(operations)
        # Always update the strip even when closed
        self._summary_strip.update_from_operations(operations)

    def _refresh(self, operations: Optional[list] = None) -> None:
        if operations is None:
            operations = self._controller.operations()
        self._summary_strip.update_from_operations(operations)
        self._rebuild_list(operations)

    def _rebuild_list(self, operations: list) -> None:
        # Clear existing cards
        while self._list_layout.count() > 1:  # keep the trailing stretch
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = self._controller
        # Render in UI-SPEC order: running → paused → queued → failed → completed/canceled
        order = [
            OperationState.RUNNING,
            OperationState.PAUSED,
            OperationState.QUEUED,
            OperationState.FAILED,
            OperationState.COMPLETED,
            OperationState.CANCELED,
        ]
        by_state: Dict[OperationState, List[QueueOperation]] = {s: [] for s in order}
        for op in operations:
            if op.state in by_state:
                by_state[op.state].append(op)

        insert_pos = 0
        for state in order:
            group = by_state[state]
            for idx, op in enumerate(group):
                # Compute positional move flags for queued operations only
                if state == OperationState.QUEUED:
                    base_state = op.action_state
                    action = replace(
                        base_state,
                        can_move_up=idx > 0,
                        can_move_down=idx < len(group) - 1,
                    )
                else:
                    action = op.action_state
                card = _QueueItemCard(
                    operation=op,
                    on_pause=c.pause,
                    on_resume=c.resume,
                    on_cancel=c.cancel,
                    on_retry=c.retry,
                    on_skip=c.skip,
                    on_inspect=c.request_inspect,
                    on_undo=self._on_undo,
                    on_move_up=c.move_up,
                    on_move_down=c.move_down,
                    action_state_override=action,
                )
                self._list_layout.insertWidget(insert_pos, card)
                insert_pos += 1

    def _on_clear_completed(self) -> None:
        self._controller.clear_completed()

    def _on_undo(self, operation_id: str) -> None:
        """Delegate undo restore to the controller's undo callback if set."""
        if hasattr(self._controller, '_undo_callback') and self._controller._undo_callback:
            self._controller._undo_callback(operation_id)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        """Reposition drawer when the top-level window is resized."""
        if event.type() == QEvent.Type.Resize and self._visible_state:
            self._reposition()
        return super().eventFilter(watched, event)

    def _reposition(self) -> None:
        """Anchor the drawer to the right edge of the parent widget's content area."""
        parent = self.parentWidget()
        if parent is None:
            return
        rect = parent.contentsRect()
        self.setGeometry(
            rect.x() + rect.width() - self.width(),
            rect.y(),
            self.width(),
            rect.height(),
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._visible_state:
            self._reposition()
