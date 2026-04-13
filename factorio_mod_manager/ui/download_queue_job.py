"""Queue-aware download job — bridges QueueController and ModDownloader.

``DownloadQueueJob`` wraps one ``QueueOperation`` and manages the full
lifecycle of a single download request: spawning a worker thread, injecting
cooperative pause/cancel events, forwarding progress updates, and reporting
completion or failure back to the shared controller.

Only one worker is alive per job at any time (T-04-08).  Retry is achieved by
enqueueing a fresh ``DownloadQueueJob``; the queue controller's ``retry()``
call resets the operation state so the tab can call ``job.start()`` again.
"""
from __future__ import annotations

import re as _re
import threading
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.queue_models import (
    OperationState,
    QueueFailure,
    QueueOperation,
)


# ---------------------------------------------------------------------------
# Private worker thread
# ---------------------------------------------------------------------------


class _DownloadThread(QThread):
    """Background thread that runs one ``ModDownloader.download_mods()`` call.

    Accepts pre-created *cancel_event* and *pause_event* so the parent job can
    cooperatively pause or cancel the download without killing the thread.
    """

    progress = Signal(int, int)          # (completed_count, total_count)
    finished = Signal(bool, list, str, str)  # (all_succeeded, failed_mod_names, exc_detail, exc_type)

    def __init__(
        self,
        mod_url: str,
        mods_folder: str,
        include_optional: bool,
        extra_mods: list,
        cancel_event: threading.Event,
        pause_event: threading.Event,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._mod_url = mod_url
        self._mods_folder = mods_folder
        self._include_optional = include_optional
        self._extra_mods = extra_mods
        self._cancel_event = cancel_event
        self._pause_event = pause_event

    def run(self) -> None:
        # Honour an early cancel (e.g. cancelled before the thread started)
        if self._cancel_event.is_set():
            self.finished.emit(False, [])
            return

        try:
            from ..core.downloader import ModDownloader
            from ..core.portal import PortalAPIError
            from ..utils.config import config as _app_config

            downloader = ModDownloader(
                self._mods_folder,
                max_workers=_app_config.get("max_workers", 4),
            )
            downloader.set_cancel_event(self._cancel_event)
            downloader.set_pause_event(self._pause_event)

            downloader.set_overall_progress_callback(
                lambda completed, total: self.progress.emit(completed, total)
            )

            m = _re.search(r"/mod/([^/?&\s]+)", self._mod_url)
            mod_name = m.group(1) if m else self._mod_url.strip()

            mod_list = [mod_name] + [m for m in self._extra_mods if m != mod_name]
            _downloaded, failed = downloader.download_mods(
                mod_list, include_optional=self._include_optional
            )

            if self._cancel_event.is_set():
                # Partial work due to cancel — treat as cancelled, not failure
                self.finished.emit(False, ["__cancelled__"], "", "")
            else:
                self.finished.emit(len(failed) == 0, failed, "", "")

        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, [], str(exc), exc.__class__.__name__)


# ---------------------------------------------------------------------------
# Public job class
# ---------------------------------------------------------------------------


class DownloadQueueJob(QObject):
    """Queue-owned execution wrapper for a single download operation.

    **Lifecycle**::

        op = QueueOperation(...)
        controller.enqueue(op)
        controller.start_next()   # transitions op → RUNNING
        job = DownloadQueueJob(op, url, folder)
        job.start(controller)     # spawns _DownloadThread

    Pause/resume/cancel are handled in two ways:

    1. Direct API — ``job.pause()`` / ``job.resume()`` / ``job.cancel()`` — called
       by the tab when it receives a signal from the drawer.
    2. Reactive — the job subscribes to ``controller.queue_changed`` and mirrors
       operation state into the cooperative events automatically.
    """

    def __init__(
        self,
        operation: QueueOperation,
        mod_url: str,
        mods_folder: str,
        include_optional: bool = False,
        extra_mods: list | None = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._mod_url = mod_url
        self._mods_folder = mods_folder
        self._include_optional = include_optional
        self._extra_mods = extra_mods or []
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker: Optional[_DownloadThread] = None

    # ------------------------------------------------------------------
    # Control surface
    # ------------------------------------------------------------------

    def start(self, controller) -> None:
        """Spawn the download worker.

        Safe to call after a ``controller.retry()`` resets the operation to
        QUEUED/RUNNING.  If a worker is already alive the call is silently
        ignored to prevent duplicate workers (T-04-08).
        """
        if self._worker is not None and self._worker.isRunning():
            return

        self._cancel_event.clear()
        self._pause_event.clear()

        worker = _DownloadThread(
            self._mod_url,
            self._mods_folder,
            self._include_optional,
            self._extra_mods,
            self._cancel_event,
            self._pause_event,
            parent=self,
        )
        self._worker = worker
        worker.progress.connect(
            lambda c, t: controller.report_progress(
                self._operation.id, int(c / t * 100) if t > 0 else 0
            )
        )
        worker.finished.connect(
            lambda ok, failed, exc_detail, exc_type: self._on_finished(ok, failed, controller, exc_detail, exc_type)
        )
        # Mirror operation state changes (pause/resume/cancel from drawer)
        controller.queue_changed.connect(self._on_queue_changed)
        worker.start()

    def pause(self) -> None:
        """Cooperatively pause the running download."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume a cooperatively paused download."""
        self._pause_event.clear()

    def cancel(self) -> None:
        """Request immediate cancellation.  Also unblocks any active pause."""
        self._cancel_event.set()
        self._pause_event.clear()

    # ------------------------------------------------------------------
    # Retry / inspect metadata
    # ------------------------------------------------------------------

    @property
    def mod_url(self) -> str:
        return self._mod_url

    @property
    def mods_folder(self) -> str:
        return self._mods_folder

    @property
    def include_optional(self) -> bool:
        return self._include_optional

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_queue_changed(self, operations: list) -> None:
        """Mirror operation state → cooperative event flags."""
        for op in operations:
            if op.id != self._operation.id:
                continue
            s = op.state
            if s == OperationState.PAUSED and not self._pause_event.is_set():
                self._pause_event.set()
            elif s == OperationState.RUNNING and self._pause_event.is_set():
                self._pause_event.clear()
            elif s == OperationState.CANCELED and not self._cancel_event.is_set():
                self._cancel_event.set()
                self._pause_event.clear()
            break

    def _on_finished(self, all_succeeded: bool, failed: list, controller, exc_detail: str = "", exc_type: str = "") -> None:
        """Route download outcome to the controller."""
        try:
            controller.queue_changed.disconnect(self._on_queue_changed)
        except RuntimeError:
            pass
        # If cancelled cooperatively, the controller already owns the state.
        if self._cancel_event.is_set():
            return

        if all_succeeded:
            controller.complete(self._operation.id)
            return

        # Build a plain-text failure payload (T-04-09 — never render as HTML)
        real_failed = [f for f in failed if f != "__cancelled__"]
        if real_failed:
            short = f"Failed: {', '.join(real_failed[:3])}"
            if len(real_failed) > 3:
                short += f" (+{len(real_failed) - 3} more)"
            detail = f"Mods that could not be downloaded: {', '.join(real_failed)}"
        elif exc_detail:
            short = f"Download error: {exc_type}" if exc_type else "Download error"
            detail = exc_detail
        else:
            short = "Download did not complete"
            detail = "The download ended without succeeding. Check your connection and retry."

        # Embed retry metadata in inspect_payload so the drawer can show it
        self._operation.inspect_payload = {
            "mod_url": self._mod_url,
            "mods_folder": self._mods_folder,
            "include_optional": str(self._include_optional),
            "failed_mods": ", ".join(real_failed),
        }

        controller.fail(
            self._operation.id,
            QueueFailure(
                short_description=short,
                detail=detail,
                exception_type=exc_type or None,
                retriable=True,
            ),
        )
