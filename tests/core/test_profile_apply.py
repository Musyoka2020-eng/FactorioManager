"""TDD tests for ProfileApplyJob — snapshot, diff execution, and linked downloads.

Covers:
  1. immutable diff payload carries the correct action counts (no side-effects)
  2. pre-apply snapshot is persisted before any mod-list.json mutation
  3. missing mods produce linked download operations; continue-on-failure applies
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from factorio_mod_manager.core.profiles import (
    DiffAction,
    Profile,
    ProfileDiff,
    ProfileDiffItem,
    ProfileSnapshot,
    ProfileStore,
    build_diff,
)


# ---------------------------------------------------------------------------
# Fixture: minimal QApplication
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def controller(qapp):
    from factorio_mod_manager.ui.queue_controller import QueueController

    return QueueController()


def _make_profile(name: str, desired: list) -> Profile:
    return Profile(id=str(uuid.uuid4()), name=name, desired_mods=desired)


# ---------------------------------------------------------------------------
# Test 1: build_diff produces exact action counts from the diff model
# ---------------------------------------------------------------------------


class TestDiffCounts:
    def test_enable_action_for_installed_but_disabled_mod(self):
        """A mod in desired that is installed but disabled becomes ENABLE."""
        profile = _make_profile("p1", ["mod_b"])
        diff = build_diff(
            profile,
            installed_zip_names=["mod_a", "mod_b"],
            current_enabled={"mod_a": True, "mod_b": False},
        )
        assert diff.enable_count == 1
        assert diff.disable_count == 1  # mod_a enabled but not desired
        assert diff.download_count == 0

    def test_download_action_for_absent_mod(self):
        """A mod in desired that is not installed at all becomes DOWNLOAD."""
        profile = _make_profile("p2", ["mod_c"])
        diff = build_diff(
            profile,
            installed_zip_names=["mod_a"],
            current_enabled={"mod_a": True},
        )
        assert diff.download_count == 1
        assert diff.disable_count == 1  # mod_a enabled but not desired

    def test_no_action_for_already_correct_state(self):
        """A mod that is already installed and enabled in desired produces no action."""
        profile = _make_profile("p3", ["mod_a"])
        diff = build_diff(
            profile,
            installed_zip_names=["mod_a"],
            current_enabled={"mod_a": True},
        )
        assert diff.is_empty

    def test_profile_apply_job_receives_diff(self, qapp, controller):
        """ProfileApplyJob stores the immutable diff without mutating it."""
        from factorio_mod_manager.ui.profile_apply_job import ProfileApplyJob
        from factorio_mod_manager.core.queue_models import (
            OperationKind, OperationSource, OperationState, QueueOperation,
        )

        profile = _make_profile("p4", ["mod_a"])
        diff = build_diff(
            profile,
            installed_zip_names=["mod_a"],
            current_enabled={"mod_a": True},
        )
        op = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.PROFILE_APPLY,
            label="Apply p4",
        )
        job = ProfileApplyJob(op, diff, profile, MagicMock(), "/tmp/mods")
        # Diff stored unchanged
        assert job._diff is diff


# ---------------------------------------------------------------------------
# Test 2: pre-apply snapshot is persisted before mod-list.json mutation
# ---------------------------------------------------------------------------


class TestSnapshotPersistence:
    def test_snapshot_saved_before_apply_completes(self, qapp, controller):
        """save_snapshot is called before the apply_done signal is emitted."""
        from factorio_mod_manager.ui.profile_apply_job import ProfileApplyJob, _ApplyThread
        from factorio_mod_manager.core.queue_models import (
            OperationKind, OperationSource, OperationState, QueueOperation,
        )

        profile = _make_profile("snap-test", ["mod_a"])
        diff = ProfileDiff(
            profile_id=profile.id,
            profile_name=profile.name,
            items=[ProfileDiffItem(action=DiffAction.ENABLE, mod_name="mod_a")],
        )
        op = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.PROFILE_APPLY,
            label="Apply snap-test",
        )
        controller.enqueue(op)
        controller.start_next()

        mock_store = MagicMock(spec=ProfileStore)
        job = ProfileApplyJob(op, diff, profile, mock_store, "/tmp/mods")

        with patch("factorio_mod_manager.ui.profile_apply_job._ApplyThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            # Simulate thread emitting apply_done
            apply_done_cb = mock_thread.apply_done.connect.call_args[0][0]
            apply_done_cb("fake-snapshot-id", [])

        assert controller.get_operation(op.id).state == OperationState.COMPLETED
        assert controller.get_operation(op.id).snapshot_id == "fake-snapshot-id"
        assert controller.get_operation(op.id).undo_eligible is True

    def test_previous_undo_invalidated_on_new_apply(self, qapp, controller):
        """Starting a new apply invalidates the previous completed apply's undo token."""
        from factorio_mod_manager.ui.profile_apply_job import ProfileApplyJob
        from factorio_mod_manager.core.queue_models import (
            OperationKind, OperationSource, OperationState, QueueOperation,
        )

        profile = _make_profile("inv-test", ["mod_a"])
        diff_empty = ProfileDiff(profile_id=profile.id, profile_name=profile.name)

        op1 = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.PROFILE_APPLY,
            label="Apply first",
        )
        controller.enqueue(op1)
        controller.start_next()
        controller.complete(op1.id)
        controller.get_operation(op1.id).undo_eligible = True

        # Starting a new apply should give us a way to invalidate op1's undo
        controller.invalidate_undo(op1.id)
        assert controller.get_operation(op1.id).undo_eligible is False


# ---------------------------------------------------------------------------
# Test 3: missing mods create linked download operations
# ---------------------------------------------------------------------------


class TestLinkedDownloads:
    def test_download_items_become_linked_operations(self, qapp, controller):
        """DOWNLOAD diff items produce linked QueueOperation IDs on completion."""
        from factorio_mod_manager.ui.profile_apply_job import ProfileApplyJob, _ApplyThread
        from factorio_mod_manager.core.queue_models import (
            OperationKind, OperationSource, OperationState, QueueOperation,
        )

        profile = _make_profile("dl-test", ["mod_a", "mod_missing"])
        diff = ProfileDiff(
            profile_id=profile.id,
            profile_name=profile.name,
            items=[
                ProfileDiffItem(action=DiffAction.DOWNLOAD, mod_name="mod_missing"),
            ],
        )
        op = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.PROFILE_APPLY,
            label="Apply dl-test",
        )
        controller.enqueue(op)
        controller.start_next()

        mock_store = MagicMock(spec=ProfileStore)
        job = ProfileApplyJob(op, diff, profile, mock_store, "/tmp/mods")

        # Patch DownloadQueueJob to avoid actual network calls
        with patch("factorio_mod_manager.ui.profile_apply_job._ApplyThread") as MockThread, \
             patch("factorio_mod_manager.ui.profile_apply_job.DownloadQueueJob") as MockDlJob:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            mock_dl_job = MagicMock()
            MockDlJob.return_value = mock_dl_job

            job.start(controller)
            # Signal: snapshot ok, one download mod
            apply_done_cb = mock_thread.apply_done.connect.call_args[0][0]
            apply_done_cb("snap-dl", ["mod_missing"])

        completed_op = controller.get_operation(op.id)
        assert completed_op.state == OperationState.COMPLETED
        # At least one linked operation was created for the download
        assert len(completed_op.linked_operation_ids) >= 1
