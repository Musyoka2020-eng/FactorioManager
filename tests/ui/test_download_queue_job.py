"""TDD tests for DownloadQueueJob.

Covers:
  1. State transitions:  RUNNING → COMPLETED / FAILED via controller
  2. Pause / cancel events:  flags set correctly, no duplicate workers
  3. Failure inspect metadata:  retriable, mod names, retry payload
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from factorio_mod_manager.core.queue_models import (
    OperationKind,
    OperationSource,
    OperationState,
    QueueOperation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication required for QObject / Signal support."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def controller(qapp):
    from factorio_mod_manager.ui.queue_controller import QueueController

    return QueueController()


def _make_op(label: str = "test-dl") -> QueueOperation:
    return QueueOperation(
        source=OperationSource.DOWNLOADER,
        kind=OperationKind.DOWNLOAD,
        state=OperationState.QUEUED,
        label=label,
    )


def _make_job(op: QueueOperation, url: str = "https://mods.factorio.com/mod/mymod",
              folder: str = "/tmp/mods", optional: bool = False):
    from factorio_mod_manager.ui.download_queue_job import DownloadQueueJob

    return DownloadQueueJob(op, url, folder, include_optional=optional)


# ---------------------------------------------------------------------------
# Helper: capture the ``finished`` callback wired during job.start()
# ---------------------------------------------------------------------------

def _start_with_mock_thread(job, controller):
    """Start the job with a mocked _DownloadThread.

    Returns ``(mock_thread, finished_callback)`` so callers can simulate
    completion without actually downloading anything.
    """
    with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = False
        MockThread.return_value = mock_thread
        job.start(controller)
        # Retrieve the callback wired to finished signal
        finished_cb = mock_thread.finished.connect.call_args[0][0]
        return mock_thread, finished_cb, MockThread


# ===========================================================================
# Test 1: State transitions  queued → running → completed / failed
# ===========================================================================


class TestStateTransitions:
    def test_completed_on_success(self, qapp, controller):
        """Successful download transitions operation to COMPLETED."""
        op = _make_op("dl-success")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            finished_cb = mock_thread.finished.connect.call_args[0][0]
            finished_cb(True, [])  # simulate success

        assert controller.get_operation(op.id).state == OperationState.COMPLETED

    def test_failed_on_download_error(self, qapp, controller):
        """Failed download transitions operation to FAILED with failure details."""
        op = _make_op("dl-fail")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            finished_cb = mock_thread.finished.connect.call_args[0][0]
            finished_cb(False, ["badmod"])

        stored = controller.get_operation(op.id)
        assert stored.state == OperationState.FAILED
        assert stored.failure is not None
        assert stored.failure.retriable is True

    def test_cancelled_download_does_not_call_complete_or_fail(self, qapp, controller):
        """When _cancel_event is set at finish time the controller is not updated."""
        op = _make_op("dl-cancel-silent")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            finished_cb = mock_thread.finished.connect.call_args[0][0]
            # Simulate cooperative cancel during download
            job._cancel_event.set()
            finished_cb(False, ["__cancelled__"])

        # State must still be RUNNING — the controller did not receive a call
        assert controller.get_operation(op.id).state == OperationState.RUNNING


# ===========================================================================
# Test 2: Pause / cancel — cooperative flags, no duplicate workers
# ===========================================================================


class TestPauseCancel:
    def test_pause_sets_only_pause_event(self, qapp):
        """pause() sets _pause_event and leaves _cancel_event alone."""
        op = _make_op("dl-pause")
        job = _make_job(op)

        assert not job._pause_event.is_set()
        assert not job._cancel_event.is_set()
        job.pause()
        assert job._pause_event.is_set()
        assert not job._cancel_event.is_set()

    def test_resume_clears_pause_event(self, qapp):
        """resume() clears _pause_event."""
        op = _make_op("dl-resume")
        job = _make_job(op)

        job.pause()
        job.resume()
        assert not job._pause_event.is_set()

    def test_cancel_sets_cancel_and_clears_pause(self, qapp):
        """cancel() sets _cancel_event and also unblocks any existing pause."""
        op = _make_op("dl-cancel")
        job = _make_job(op)

        job.pause()  # pause first so cancel has to clear it
        job.cancel()
        assert job._cancel_event.is_set()
        assert not job._pause_event.is_set()  # unblocked by cancel

    def test_second_start_does_not_create_duplicate_worker(self, qapp, controller):
        """Calling start() while a worker is alive is silently ignored."""
        op = _make_op("dl-no-dup")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = True  # pretend worker is alive
            MockThread.return_value = mock_thread

            job.start(controller)   # first call — creates worker
            job.start(controller)   # second call — must be ignored
            # Constructor must have been called only once
            assert MockThread.call_count == 1

    def test_events_cleared_on_fresh_start(self, qapp, controller):
        """_cancel_event and _pause_event are cleared before a new worker starts."""
        op = _make_op("dl-fresh-start")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)
        # Pre-set both flags
        job._cancel_event.set()
        job._pause_event.set()

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)

        assert not job._cancel_event.is_set()
        assert not job._pause_event.is_set()


# ===========================================================================
# Test 3: Failure inspect details and retry metadata
# ===========================================================================


class TestFailureInspectMetadata:
    def test_failure_short_description_includes_failed_mod_names(self, qapp, controller):
        """QueueFailure.short_description names the failed mods."""
        op = _make_op("dl-inspect")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            cb = mock_thread.finished.connect.call_args[0][0]
            cb(False, ["mod_a", "mod_b"])

        failure = controller.get_operation(op.id).failure
        assert "mod_a" in failure.short_description
        assert "mod_b" in failure.short_description

    def test_inspect_payload_contains_retry_metadata(self, qapp, controller):
        """Failed operation inspect_payload holds url, folder, and failed mods."""
        url = "https://mods.factorio.com/mod/fancy_mod"
        folder = "/tmp/my_mods"
        op = _make_op("dl-retry-payload")
        controller.enqueue(op)
        controller.start_next()
        job = _make_job(op, url=url, folder=folder)

        with patch("factorio_mod_manager.ui.download_queue_job._DownloadThread") as MockThread:
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = False
            MockThread.return_value = mock_thread
            job.start(controller)
            cb = mock_thread.finished.connect.call_args[0][0]
            cb(False, ["fancy_mod"])

        payload = controller.get_operation(op.id).inspect_payload
        assert payload["mod_url"] == url
        assert payload["mods_folder"] == folder
        assert "fancy_mod" in payload["failed_mods"]

    def test_retry_metadata_properties(self, qapp):
        """Job exposes mod_url, mods_folder, include_optional as properties."""
        url = "https://mods.factorio.com/mod/thing"
        folder = "/tmp/myfolder"
        op = _make_op("dl-props")
        job = _make_job(op, url=url, folder=folder, optional=True)

        assert job.mod_url == url
        assert job.mods_folder == folder
        assert job.include_optional is True