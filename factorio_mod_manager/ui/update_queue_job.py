"""Queue-aware update job — bridges QueueController and CheckerLogic.update_mods().

``UpdateQueueJob`` wraps one ``QueueOperation`` for a bulk mod update and
manages the full lifecycle: spawning a worker thread, forwarding completion,
and reporting failure back to the shared controller with retry metadata.

Cancel is cooperative — if the cancel event is set before the thread
starts the job exits immediately without running the update.
"""
from __future__ import annotations

import threading
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.queue_models import (
    OperationState,
    QueueFailure,
    QueueOperation,
)


# ---------------------------------------------------------------------------
# Private worker
# ---------------------------------------------------------------------------


class _UpdateThread(QThread):
    """Runs ``CheckerLogic.update_mods()`` in a background thread."""

    finished = Signal(bool, list)  # (all_succeeded, failed_mod_names)

    def __init__(
        self,
        checker_logic,
        mod_names: List[str],
        cancel_event: threading.Event,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._logic = checker_logic
        self._mod_names = list(mod_names)
        self._cancel_event = cancel_event

    def run(self) -> None:
        if self._cancel_event.is_set():
            self.finished.emit(False, list(self._mod_names))
            return
        try:
            _, failed = self._logic.update_mods(self._mod_names)
            if self._cancel_event.is_set():
                self.finished.emit(False, [])
                return
            self.finished.emit(len(failed) == 0, failed)
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, list(self._mod_names))


# ---------------------------------------------------------------------------
# Public job class
# ---------------------------------------------------------------------------


class UpdateQueueJob(QObject):
    """Queue-owned execution wrapper for a batch mod update.

    **Lifecycle**::

        op = QueueOperation(kind=OperationKind.UPDATE, ...)
        controller.enqueue(op)
        controller.start_next()  # op → RUNNING
        job = UpdateQueueJob(op, mod_names, checker_logic)
        job.start(controller)

    Cancel propagates cooperatively via ``_cancel_event``; pause is not
    supported for updates (updates are not chunked).
    """

    def __init__(
        self,
        operation: QueueOperation,
        mod_names: List[str],
        checker_logic,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._mod_names = list(mod_names)
        self._checker_logic = checker_logic
        self._cancel_event = threading.Event()
        self._worker: Optional[_UpdateThread] = None

    # ------------------------------------------------------------------
    # Control surface
    # ------------------------------------------------------------------

    def start(self, controller) -> None:
        """Spawn the update worker (idempotent – safe if already running)."""
        if self._worker is not None and self._worker.isRunning():
            return

        self._cancel_event.clear()

        worker = _UpdateThread(
            self._checker_logic,
            self._mod_names,
            self._cancel_event,
            parent=self,
        )
        self._worker = worker
        worker.finished.connect(
            lambda ok, failed: self._on_finished(ok, failed, controller)
        )
        # Watch for cancel from the drawer
        controller.queue_changed.connect(self._on_queue_changed)
        worker.start()

    def cancel(self) -> None:
        """Request cancellation of the running update."""
        self._cancel_event.set()

    # ------------------------------------------------------------------
    # Retry metadata
    # ------------------------------------------------------------------

    @property
    def mod_names(self) -> List[str]:
        return list(self._mod_names)

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_queue_changed(self, operations: list) -> None:
        for op in operations:
            if op.id != self._operation.id:
                continue
            if op.state == OperationState.CANCELED and not self._cancel_event.is_set():
                self._cancel_event.set()
            break

    def _on_finished(self, all_succeeded: bool, failed: list, controller) -> None:
        try:
            controller.queue_changed.disconnect(self._on_queue_changed)
        except RuntimeError:
            pass
        if self._cancel_event.is_set():
            return  # controller already owns state

        if all_succeeded:
            controller.complete(self._operation.id)
            return

        # Plain-text failure payload (T-04-11)
        real_failed = [f for f in failed if f]
        if real_failed:
            short = f"Update failed: {', '.join(real_failed[:3])}"
            if len(real_failed) > 3:
                short += f" (+{len(real_failed) - 3} more)"
            detail = f"Mods that could not be updated: {', '.join(real_failed)}"
        else:
            short = "Update did not complete"
            detail = "The update ended without succeeding."

        self._operation.inspect_payload = {
            "mod_names": ", ".join(self._mod_names),
            "failed_mods": ", ".join(real_failed),
        }

        controller.fail(
            self._operation.id,
            QueueFailure(short_description=short, detail=detail, retriable=True),
        )
