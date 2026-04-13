"""Shared queue controller — owns QueueOperation lifecycle and signals.

This QObject is instantiated once by MainWindow and shared across all
workflow tabs (Downloader, Checker, Profile Apply).  It manages state
transitions, enforces ordering rules (running items cannot be reordered),
and broadcasts snapshot/badge/drawer signals for UI consumers.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from ..core.queue_models import (
    OperationState,
    QueueFailure,
    QueueOperation,
    QueueResult,
)

logger = logging.getLogger(__name__)


class QueueController(QObject):
    """Single source of truth for the application-wide operation queue.

    Signals
    -------
    queue_changed
        Emitted after any state mutation. Payload: current operation list.
    badge_count_changed
        Emitted when the visible badge count changes. Payload: (count, has_failed).
    drawer_open_requested
        Emitted when a component wants to open the queue drawer.
    inspect_requested
        Emitted when the user clicks Inspect on an item. Payload: operation id.
    """

    queue_changed = Signal(list)           # List[QueueOperation]
    badge_count_changed = Signal(int, bool)  # (count, has_failed)
    drawer_open_requested = Signal()
    inspect_requested = Signal(str)         # operation id

    # Completed / canceled items are retained in the drawer for this many
    # items before oldest are pruned.
    _RETENTION_LIMIT = 50

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        # Ordered list: earlier == higher priority in queue
        self._operations: List[QueueOperation] = []

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(self, operation: QueueOperation) -> str:
        """Add *operation* to the end of the queue and return its id."""
        self._operations.append(operation)
        self._emit_badge()
        self.queue_changed.emit(list(self._operations))
        return operation.id

    def batch_enqueue(self, operations: List[QueueOperation]) -> List[str]:
        """Add multiple operations and emit ``queue_changed`` exactly once.

        Avoids N synchronous ``queue_changed`` emissions when enqueuing a
        batch of resolved dependencies at once.
        """
        ids: List[str] = []
        for op in operations:
            self._operations.append(op)
            ids.append(op.id)
        if operations:
            self._emit_badge()
            self.queue_changed.emit(list(self._operations))
        return ids

    def update_label(self, operation_id: str, new_label: str) -> None:
        """Update the display label of an operation and emit ``queue_changed``."""
        op = self._by_id(operation_id)
        if op is not None:
            op.label = new_label
            self.queue_changed.emit(list(self._operations))

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def start_next(self) -> Optional[QueueOperation]:
        """Transition the first QUEUED item to RUNNING and return it, or None."""
        for op in self._operations:
            if op.state == OperationState.QUEUED:
                op.state = OperationState.RUNNING
                self._notify()
                return op
        return None

    def start_up_to(self, n: int) -> List[QueueOperation]:
        """Transition up to *n* QUEUED items to RUNNING and return them."""
        started: List[QueueOperation] = []
        for op in self._operations:
            if len(started) >= n:
                break
            if op.state == OperationState.QUEUED:
                op.state = OperationState.RUNNING
                started.append(op)
        if started:
            self._notify()
        return started

    def report_progress(self, operation_id: str, progress: int) -> None:
        """Update progress (0-100) for a running operation."""
        op = self._by_id(operation_id)
        if op and op.state == OperationState.RUNNING:
            op.progress = max(0, min(100, progress))
            self.queue_changed.emit(list(self._operations))

    def complete(self, operation_id: str, result: Optional[QueueResult] = None) -> None:
        """Mark operation as COMPLETED, optionally attaching undo metadata."""
        op = self._by_id(operation_id)
        if op is None:
            return
        # Guard: only transition from RUNNING or PAUSED
        if op.state not in (OperationState.RUNNING, OperationState.PAUSED):
            return
        op.state = OperationState.COMPLETED
        op.progress = 100
        if result:
            op.snapshot_id = result.snapshot_id
            op.undo_eligible = result.snapshot_id is not None
            op.linked_operation_ids = result.linked_operation_ids or []
        self._prune_terminal()
        self._notify()

    def fail(self, operation_id: str, failure: QueueFailure) -> None:
        """Mark operation as FAILED with recoverable *failure* details."""
        op = self._by_id(operation_id)
        if op is None:
            return
        # Guard: only transition from RUNNING or PAUSED
        if op.state not in (OperationState.RUNNING, OperationState.PAUSED):
            return
        op.state = OperationState.FAILED
        op.failure = failure
        self._notify()

    def pause(self, operation_id: str) -> bool:
        """Pause a RUNNING operation. Returns True if transition was legal."""
        op = self._by_id(operation_id)
        if op and op.state == OperationState.RUNNING:
            op.state = OperationState.PAUSED
            self._notify()
            return True
        return False

    def resume(self, operation_id: str) -> bool:
        """Resume a PAUSED operation. Returns True if transition was legal."""
        op = self._by_id(operation_id)
        if op and op.state == OperationState.PAUSED:
            op.state = OperationState.RUNNING
            self._notify()
            return True
        return False

    def cancel(self, operation_id: str) -> bool:
        """Cancel a QUEUED, RUNNING, or PAUSED operation."""
        op = self._by_id(operation_id)
        if op and op.state in (
            OperationState.QUEUED, OperationState.RUNNING, OperationState.PAUSED
        ):
            # Guard: operation is not already terminal
            if op.state in (OperationState.COMPLETED, OperationState.CANCELED, OperationState.FAILED):
                return False
            op.state = OperationState.CANCELED
            self._prune_terminal()
            self._notify()
            return True
        return False

    def retry(self, operation_id: str) -> bool:
        """Move a FAILED operation back to QUEUED for re-execution."""
        op = self._by_id(operation_id)
        if op and op.state == OperationState.FAILED and op.action_state.can_retry:
            op.state = OperationState.QUEUED
            op.failure = None
            op.progress = None
            op.inspect_payload = {}
            self._notify()
            return True
        return False

    def skip(self, operation_id: str) -> bool:
        """Move a FAILED operation to CANCELED (skip without retry)."""
        op = self._by_id(operation_id)
        if op and op.state == OperationState.FAILED:
            op.state = OperationState.CANCELED
            self._prune_terminal()
            self._notify()
            return True
        return False

    def clear_completed(self) -> int:
        """Remove all COMPLETED and CANCELED items. Returns count removed."""
        before = len(self._operations)
        self._operations = [
            op for op in self._operations
            if op.state not in (OperationState.COMPLETED, OperationState.CANCELED)
        ]
        removed = before - len(self._operations)
        if removed:
            self._notify()
        return removed

    # ------------------------------------------------------------------
    # Reorder (queued items only; pinned while running)
    # ------------------------------------------------------------------

    def move_up(self, operation_id: str) -> bool:
        """Move a QUEUED item one position earlier in the queue."""
        idx = self._index_of(operation_id)
        if idx is None:
            return False
        op = self._operations[idx]
        if op.state != OperationState.QUEUED:
            return False
        # Find the closest QUEUED item above
        target = idx - 1
        while target >= 0 and self._operations[target].state != OperationState.QUEUED:
            target -= 1
        if target < 0:
            return False
        self._operations[idx], self._operations[target] = (
            self._operations[target], self._operations[idx]
        )
        self._notify()
        return True

    def move_down(self, operation_id: str) -> bool:
        """Move a QUEUED item one position later in the queue."""
        idx = self._index_of(operation_id)
        if idx is None:
            return False
        op = self._operations[idx]
        if op.state != OperationState.QUEUED:
            return False
        target = idx + 1
        while target < len(self._operations) and self._operations[target].state != OperationState.QUEUED:
            target += 1
        if target >= len(self._operations):
            return False
        self._operations[idx], self._operations[target] = (
            self._operations[target], self._operations[idx]
        )
        self._notify()
        return True

    # ------------------------------------------------------------------
    # Undo support
    # ------------------------------------------------------------------

    def invalidate_undo(self, operation_id: str) -> None:
        """Remove undo eligibility from a completed operation."""
        op = self._by_id(operation_id)
        if op:
            op.undo_eligible = False
            op.snapshot_id = None
            self._notify()

    # ------------------------------------------------------------------
    # Drawer helpers
    # ------------------------------------------------------------------

    def request_open_drawer(self) -> None:
        """Ask the shell to open the queue drawer."""
        self.drawer_open_requested.emit()

    def request_inspect(self, operation_id: str) -> None:
        """Emit inspect request for *operation_id*."""
        self.inspect_requested.emit(operation_id)

    # ------------------------------------------------------------------
    # Badge count helpers
    # ------------------------------------------------------------------

    def badge_count(self) -> int:
        """Number of items that contribute to the active queue count.

        Includes: queued, running, paused, failed-awaiting-action.
        Excludes: completed and canceled (after retention cleanup).
        """
        return sum(
            1 for op in self._operations
            if op.state in (
                OperationState.QUEUED,
                OperationState.RUNNING,
                OperationState.PAUSED,
                OperationState.FAILED,
            )
        )

    def has_failed(self) -> bool:
        return any(op.state == OperationState.FAILED for op in self._operations)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def operations(self) -> List[QueueOperation]:
        return list(self._operations)

    def get_operation(self, operation_id: str) -> Optional[QueueOperation]:
        return self._by_id(operation_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _by_id(self, operation_id: str) -> Optional[QueueOperation]:
        for op in self._operations:
            if op.id == operation_id:
                return op
        return None

    def _index_of(self, operation_id: str) -> Optional[int]:
        for i, op in enumerate(self._operations):
            if op.id == operation_id:
                return i
        return None

    def _prune_terminal(self) -> None:
        """Prune oldest terminal items when retention limit is exceeded."""
        terminal = [
            i for i, op in enumerate(self._operations)
            if op.state in (OperationState.COMPLETED, OperationState.CANCELED)
        ]
        excess = len(terminal) - self._RETENTION_LIMIT
        if excess > 0 and terminal:
            to_remove = set(terminal[:excess])
            self._operations = [
                op for i, op in enumerate(self._operations) if i not in to_remove
            ]

    def _notify(self) -> None:
        self._emit_badge()
        self.queue_changed.emit(list(self._operations))

    def _emit_badge(self) -> None:
        self.badge_count_changed.emit(self.badge_count(), self.has_failed())