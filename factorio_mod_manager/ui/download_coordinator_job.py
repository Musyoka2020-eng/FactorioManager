"""Coordinator job: resolve deps then download all files in ONE queue operation.

``DownloadCoordinatorJob`` replaces the old ``ResolveQueueJob`` +
``SingleFileDownloadJob`` pair.  It exposes exactly **one** ``QueueOperation``
to the queue controller, keeping the queue drawer from receiving N emissions
when a batch of mods is being downloaded.

Flow:
  Phase A — ``_CoordinatorThread`` calls ``ModDownloader.resolve_dependencies``
             for the requested mod and any user-selected optional deps.
             On success it updates the queue label to show the resolved count
             and emits ``label_changed``.

  Phase B — a ``ThreadPoolExecutor`` downloads all resolved files in parallel
             (``max_workers`` from app config).  Each completed file emits
             ``file_done``; overall progress is reported via ``progress(n, total)``.

Cancel / pause are handled by cooperative ``threading.Event`` objects that
are injected into the ``ModDownloader`` instance before Phase B starts.
"""
from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.mod import Mod
from ..core.queue_models import OperationSource, OperationKind, OperationState, QueueFailure, QueueOperation


# ---------------------------------------------------------------------------
# Private worker thread
# ---------------------------------------------------------------------------


class _CoordinatorThread(QThread):
    """Background thread: resolve deps then parallel-download all files."""

    label_changed = Signal(str)        # e.g. "Download Krastorio2 + 5 deps"
    progress = Signal(int, int)        # (completed_files, total_files)
    file_done = Signal(str, bool)      # (mod_name, success)
    finished = Signal(bool, list)      # (all_ok, failed_mod_names)

    def __init__(
        self,
        mod_name: str,
        selected_optionals: List[str],
        mods_folder: str,
        cancel_event: threading.Event,
        pause_event: threading.Event,
        max_workers: int,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._mod_name = mod_name
        self._selected_optionals = selected_optionals
        self._mods_folder = mods_folder
        self._cancel_event = cancel_event
        self._pause_event = pause_event
        self._max_workers = max_workers

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        # ── Phase A: dependency resolution ────────────────────────────
        try:
            mods = self._resolve()
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, [str(exc)])
            return

        if mods is None:
            # Canceled during resolve
            self.finished.emit(False, [])
            return

        if not mods:
            # Nothing to download — already installed
            self.finished.emit(True, [])
            return

        dep_count = len(mods) - 1
        if dep_count > 0:
            self.label_changed.emit(f"Download {self._mod_name} + {dep_count} dep{'s' if dep_count != 1 else ''}")
        else:
            self.label_changed.emit(f"Download {self._mod_name}")

        # ── Phase B: parallel download ─────────────────────────────────
        failed: List[str] = []
        total = len(mods)
        completed = 0
        self.progress.emit(0, total)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            future_to_mod: dict[Future, Mod] = {
                pool.submit(self._download_one, mod): mod for mod in mods
            }
            for future in as_completed(future_to_mod):
                if self._cancel_event.is_set():
                    # Cancel all remaining futures
                    for f in future_to_mod:
                        f.cancel()
                    self.finished.emit(False, [])
                    return

                mod = future_to_mod[future]
                try:
                    ok = future.result()
                except Exception as exc:  # noqa: BLE001
                    ok = False

                completed += 1
                self.file_done.emit(mod.name, ok)
                self.progress.emit(completed, total)
                if not ok:
                    failed.append(mod.name)

        self.finished.emit(len(failed) == 0, failed)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve(self) -> Optional[List[Mod]]:
        """Return list of Mod objects to download, or None if canceled."""
        from ..core.downloader import ModDownloader

        downloader = ModDownloader(self._mods_folder)
        downloader.set_cancel_event(self._cancel_event)

        if self._cancel_event.is_set():
            return None

        deps, _incompats, _expansions = downloader.resolve_dependencies(
            self._mod_name, include_optional=False
        )

        if self._cancel_event.is_set():
            return None

        for opt_name in self._selected_optionals:
            if opt_name == self._mod_name or opt_name in deps:
                continue
            opt_deps, _, _ = downloader.resolve_dependencies(
                opt_name, include_optional=False
            )
            deps.update(opt_deps)
            if self._cancel_event.is_set():
                return None

        return list(deps.values())

    def _download_one(self, mod: Mod) -> bool:
        """Download a single mod file.  Runs inside the thread pool."""
        from ..core.downloader import ModDownloader

        # Respect pause by blocking until unpaused (checked periodically)
        while self._pause_event.is_set() and not self._cancel_event.is_set():
            import time
            time.sleep(0.1)

        if self._cancel_event.is_set():
            return False

        try:
            downloader = ModDownloader(self._mods_folder, max_workers=1)
            downloader.set_cancel_event(self._cancel_event)
            downloader.set_pause_event(self._pause_event)
            return bool(downloader.download_mod(mod))
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Public job class
# ---------------------------------------------------------------------------


class DownloadCoordinatorJob(QObject):
    """Queue-owned wrapper that manages one full download session.

    Exposes exactly **one** ``QueueOperation`` to the controller so the
    queue drawer receives at most one ``queue_changed`` emission per
    download session (instead of one per resolved file).

    Signals
    -------
    log_message(str, str)
        Forwarded messages for the inline console: ``(text, level)``.
    finished_op(str)
        Emitted after the job fully completes (success, failure, or cancel).
        Payload is the operation id.
    """

    log_message = Signal(str, str)  # (message, level)
    finished_op = Signal(str)       # op_id

    def __init__(
        self,
        operation: QueueOperation,
        mod_name: str,
        selected_optionals: List[str],
        mods_folder: str,
        max_workers: int = 4,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._mod_name = mod_name
        self._selected_optionals = selected_optionals
        self._mods_folder = mods_folder
        self._max_workers = max_workers
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker: Optional[_CoordinatorThread] = None
        self._controller = None  # set in start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def operation_id(self) -> str:
        return self._operation.id

    def start(self, controller) -> None:
        """Spawn the coordinator thread.  Safe to call once per job."""
        if self._worker is not None and self._worker.isRunning():
            return

        self._controller = controller
        self._cancel_event.clear()
        self._pause_event.clear()

        worker = _CoordinatorThread(
            self._mod_name,
            self._selected_optionals,
            self._mods_folder,
            self._cancel_event,
            self._pause_event,
            self._max_workers,
            parent=self,
        )
        self._worker = worker

        worker.label_changed.connect(
            lambda lbl: controller.update_label(self._operation.id, lbl)
        )
        worker.progress.connect(
            lambda c, t: controller.report_progress(
                self._operation.id, int(c / t * 100) if t > 0 else 0
            )
        )
        worker.file_done.connect(
            lambda name, ok: self.log_message.emit(
                f"{'✓' if ok else '✗'} {name}",
                "SUCCESS" if ok else "ERROR",
            )
        )
        worker.finished.connect(
            lambda ok, failed: self._on_finished(ok, failed, controller)
        )

        # React to pause/resume/cancel from the queue drawer
        controller.queue_changed.connect(self._on_queue_changed)

        worker.start()

    def pause(self) -> None:
        """Cooperatively pause all running downloads."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume from a cooperative pause."""
        self._pause_event.clear()

    def cancel(self) -> None:
        """Request cancellation of resolve and all downloads."""
        self._cancel_event.set()
        self._pause_event.clear()

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_queue_changed(self, operations: list) -> None:
        """Mirror pause/resume/cancel from controller into cooperative events."""
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

    def _on_finished(self, all_ok: bool, failed: List[str], controller) -> None:
        """Called on the main thread (Qt cross-thread signal delivery)."""
        try:
            controller.queue_changed.disconnect(self._on_queue_changed)
        except RuntimeError:
            pass

        if self._cancel_event.is_set():
            # Controller already holds CANCELED state; nothing to do
            pass
        elif all_ok:
            controller.complete(self._operation.id)
        else:
            desc = f"Failed: {', '.join(failed)}" if failed else "Download failed"
            controller.fail(
                self._operation.id,
                QueueFailure(short_description=desc),
            )

        self.finished_op.emit(self._operation.id)
