"""Tests for QueueController — state machine and badge counts.

These tests run headless using a minimal Qt application fixture so PySide6
signals work correctly without a display.
"""
import pytest
from factorio_mod_manager.core.queue_models import (
    OperationKind,
    OperationSource,
    OperationState,
    QueueFailure,
    QueueOperation,
)


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication for signal/slot tests."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def controller(qapp):
    from factorio_mod_manager.ui.queue_controller import QueueController
    return QueueController()


def make_op(**kwargs) -> QueueOperation:
    defaults = dict(
        source=OperationSource.DOWNLOADER,
        kind=OperationKind.DOWNLOAD,
        state=OperationState.QUEUED,
        label="test-op",
    )
    defaults.update(kwargs)
    return QueueOperation(**defaults)


# ---------------------------------------------------------------------------
# Test 1: reorder — queued items move; running items are pinned
# ---------------------------------------------------------------------------

def test_queued_items_can_move_up(controller) -> None:
    a = make_op(label="A")
    b = make_op(label="B")
    controller.enqueue(a)
    controller.enqueue(b)
    assert controller.operations()[0].id == a.id
    controller.move_down(a.id)
    ops = controller.operations()
    assert ops[0].id == b.id
    assert ops[1].id == a.id


def test_queued_items_can_move_down(controller) -> None:
    controller.clear_completed()
    a = make_op(label="A2")
    b = make_op(label="B2")
    controller.enqueue(a)
    controller.enqueue(b)
    controller.move_down(a.id)
    ops_after = [op for op in controller.operations() if op.id in (a.id, b.id)]
    assert ops_after[0].id == b.id


def test_running_item_cannot_be_reordered(controller) -> None:
    controller.clear_completed()
    op = make_op(label="Running")
    controller.enqueue(op)
    controller.start_next()
    assert controller.get_operation(op.id).state == OperationState.RUNNING
    result = controller.move_up(op.id)
    assert result is False


# ---------------------------------------------------------------------------
# Test 2: legal state transitions only; continue-on-failure semantics
# ---------------------------------------------------------------------------

def test_pause_resume_cycle(controller) -> None:
    op = make_op(label="PR")
    controller.enqueue(op)
    controller.start_next()
    assert controller.pause(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.PAUSED
    assert controller.resume(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.RUNNING


def test_cannot_pause_queued_item(controller) -> None:
    op = make_op(label="NoPause")
    controller.enqueue(op)
    assert controller.pause(op.id) is False


def test_cancel_queued_item(controller) -> None:
    op = make_op(label="CancelQ")
    controller.enqueue(op)
    assert controller.cancel(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.CANCELED


def test_cancel_running_item(controller) -> None:
    op = make_op(label="CancelR")
    controller.enqueue(op)
    controller.start_next()
    assert controller.cancel(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.CANCELED


def test_retry_failed_item(controller) -> None:
    op = make_op(label="Retry")
    controller.enqueue(op)
    controller.start_next()
    controller.fail(op.id, QueueFailure(short_description="oops", retriable=True))
    assert controller.retry(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.QUEUED


def test_skip_failed_item(controller) -> None:
    op = make_op(label="Skip")
    controller.enqueue(op)
    controller.start_next()
    controller.fail(op.id, QueueFailure(short_description="oops", retriable=True))
    assert controller.skip(op.id) is True
    assert controller.get_operation(op.id).state == OperationState.CANCELED


def test_continue_on_failure_default_is_true(controller) -> None:
    op = make_op(label="COF")
    controller.enqueue(op)
    assert op.continue_on_failure is True


# ---------------------------------------------------------------------------
# Test 3: badge counts include queued/running/paused/failed; exclude completed/canceled
# ---------------------------------------------------------------------------

def test_badge_count_includes_active_states(controller) -> None:
    controller.clear_completed()
    initial_badge = controller.badge_count()

    q_op = make_op(label="Q")
    controller.enqueue(q_op)
    assert controller.badge_count() == initial_badge + 1

    controller.start_next()
    assert controller.badge_count() == initial_badge + 1  # still 1 (running)


def test_badge_count_excludes_completed(controller) -> None:
    controller.clear_completed()
    op = make_op(label="BComplete")
    controller.enqueue(op)
    controller.start_next()
    pre_count = controller.badge_count()
    controller.complete(op.id)
    assert controller.badge_count() == pre_count - 1


def test_badge_count_excludes_canceled(controller) -> None:
    controller.clear_completed()
    op = make_op(label="BCancel")
    controller.enqueue(op)
    pre_count = controller.badge_count()
    controller.cancel(op.id)
    assert controller.badge_count() == pre_count - 1


def test_has_failed_reflects_failed_items(controller) -> None:
    controller.clear_completed()
    # Remove any lingering failed items
    for op in list(controller.operations()):
        if op.state == OperationState.FAILED:
            controller.skip(op.id)
    assert controller.has_failed() is False
    op = make_op(label="Fail")
    controller.enqueue(op)
    controller.start_next()
    controller.fail(op.id, QueueFailure(short_description="err"))
    assert controller.has_failed() is True
    controller.skip(op.id)
    assert controller.has_failed() is False