"""Queue-owned profile apply executor with snapshot and linked downloads.

``ProfileApplyJob`` wraps one ``QueueOperation`` for a profile apply action.
It executes the immutable ``ProfileDiff`` payload, persisting a pre-apply
snapshot before any mutation so the undo restore action can be offered after
a successful apply (D-13).

Execution sequence
------------------
1. ``_ApplyThread`` loads the current ``mod-list.json`` state and persists a
   ``ProfileSnapshot`` before touching any files.
2. Local ENABLE / DISABLE changes are applied atomically via ``ModListStore``.
3. DOWNLOAD items become linked ``DownloadQueueJob`` operations enqueued under
   the same controller with ``continue_on_failure=True`` (D-04).
4. The apply operation itself completes immediately; downloads run in parallel.

The caller is responsible for invalidating the *previous* apply's undo token
before starting a new apply (T-04-14).
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.mod_list import ModListStore
from ..core.profiles import DiffAction, ProfileDiff, Profile, ProfileSnapshot
from ..core.queue_models import (
    OperationKind,
    OperationSource,
    OperationState,
    QueueFailure,
    QueueOperation,
    QueueResult,
)

# Imported at module level so tests can patch via module reference.
# (Circular import is safe: profile_apply_job → download_queue_job → downloader;
#  no reverse dependency.)
from .download_queue_job import DownloadQueueJob  # noqa: E402


# ---------------------------------------------------------------------------
# Private worker thread
# ---------------------------------------------------------------------------


class _ApplyThread(QThread):
    """Applies local ENABLE / DISABLE changes and signals back snapshot + download list."""

    apply_done = Signal(str, list)   # (snapshot_id, [download_mod_names])
    apply_failed = Signal(str)       # error message

    def __init__(
        self,
        diff: "ProfileDiff",
        profile: "Profile",
        profile_store,
        mods_folder: str,
        installed_mods: Optional[Dict[str, Any]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._diff = diff
        self._profile = profile
        self._profile_store = profile_store
        self._mods_folder = mods_folder
        self._installed_mods = installed_mods or {}

    def run(self) -> None:
        try:
            ml = ModListStore(Path(self._mods_folder))

            # 1. Capture pre-apply state for undo snapshot (T-04-14)
            enabled_before = ml.load()
            snapshot = ProfileSnapshot(
                id=str(uuid.uuid4()),
                profile_id=self._profile.id,
                profile_name=self._profile.name,
                enabled_before=dict(enabled_before),
            )
            # Persist snapshot BEFORE any mutation
            self._profile_store.save_snapshot(snapshot)

            # 2. Apply local state changes — update mod-list.json AND rename ZIPs
            download_mods: List[str] = []
            for item in self._diff.items:
                if item.action in (DiffAction.ENABLE, DiffAction.ADD):
                    ml.enable(item.mod_name)
                    self._rename_zip(item.mod_name, enable=True)
                elif item.action in (DiffAction.DISABLE, DiffAction.REMOVE):
                    ml.disable(item.mod_name)
                    self._rename_zip(item.mod_name, enable=False)
                elif item.action == DiffAction.DOWNLOAD:
                    download_mods.append(item.mod_name)

            self.apply_done.emit(snapshot.id, download_mods)

        except Exception as exc:  # noqa: BLE001
            self.apply_failed.emit(str(exc))

    def _rename_zip(self, mod_name: str, *, enable: bool) -> None:
        """Rename .zip.bak -> .zip (enable) or .zip -> .zip.bak (disable) if the mod
        is in the installed_mods map and has a physical file path.

        Raises OSError if the rename fails to keep on-disk and logical state in sync.
        """
        mod = self._installed_mods.get(mod_name)
        if mod is None or not getattr(mod, "file_path", None):
            return
        file_path = Path(mod.file_path)
        if enable:
            if file_path.name.endswith(".zip.bak"):
                new_path = file_path.with_suffix("")  # strip .bak
                # Do NOT mutate mod state before successful rename
                file_path.rename(new_path)
                # Only update in-memory state after successful rename
                mod.file_path = str(new_path)
                mod.enabled = True
        else:
            if file_path.name.endswith(".zip") and not file_path.name.endswith(".zip.bak"):
                new_path = Path(str(file_path) + ".bak")
                # Do NOT mutate mod state before successful rename
                file_path.rename(new_path)
                # Only update in-memory state after successful rename
                mod.file_path = str(new_path)
                mod.enabled = False


# ---------------------------------------------------------------------------
# Public job class
# ---------------------------------------------------------------------------


class ProfileApplyJob(QObject):
    """Queue-owned executor for one profile apply.

    After ``start(controller)`` is called, the apply runs in a background
    thread, creates linked download operations for any missing mods, and
    completes the operation with snapshot metadata for undo eligibility.
    """

    def __init__(
        self,
        operation: QueueOperation,
        diff: ProfileDiff,
        profile: Profile,
        profile_store,
        mods_folder: str,
        installed_mods: Optional[Dict[str, Any]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._diff = diff
        self._profile = profile
        self._profile_store = profile_store
        self._mods_folder = mods_folder
        self._installed_mods = installed_mods or {}
        self._worker: Optional[_ApplyThread] = None

    # ------------------------------------------------------------------
    # Control surface
    # ------------------------------------------------------------------

    def start(self, controller) -> None:
        """Execute the apply in a background thread (idempotent guard)."""
        if self._worker is not None and self._worker.isRunning():
            return

        worker = _ApplyThread(
            self._diff,
            self._profile,
            self._profile_store,
            self._mods_folder,
            installed_mods=self._installed_mods,
            parent=self,
        )
        self._worker = worker
        worker.apply_done.connect(
            lambda snap_id, dl_mods: self._on_apply_done(snap_id, dl_mods, controller)
        )
        worker.apply_failed.connect(
            lambda msg: self._on_apply_failed(msg, controller)
        )
        worker.start()

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_apply_done(
        self, snapshot_id: str, download_mods: List[str], controller
    ) -> None:
        """Apply succeeded — enqueue linked downloads and complete the operation."""
        linked_ids: List[str] = []

        for mod_name in download_mods:
            dl_op = QueueOperation(
                source=OperationSource.DOWNLOADER,
                kind=OperationKind.DOWNLOAD,
                label=f"Download {mod_name} (profile)",
                continue_on_failure=True,  # D-04
            )
            dl_job = DownloadQueueJob(
                dl_op,
                f"https://mods.factorio.com/mod/{mod_name}",
                self._mods_folder,
                parent=self,
            )
            controller.enqueue(dl_op)
            controller.start_next()
            dl_job.start(controller)
            linked_ids.append(dl_op.id)

        controller.complete(
            self._operation.id,
            QueueResult(
                operation_id=self._operation.id,
                state=OperationState.COMPLETED,
                snapshot_id=snapshot_id,
                linked_operation_ids=linked_ids,
            ),
        )

    def _on_apply_failed(self, message: str, controller) -> None:
        controller.fail(
            self._operation.id,
            QueueFailure(
                short_description="Profile apply failed",
                detail=message,
                retriable=True,
            ),
        )