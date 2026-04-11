"""Tests for shared queue operation contracts."""
import pytest
from factorio_mod_manager.core.queue_models import (
    OperationSource,
    OperationKind,
    OperationState,
    QueueFailure,
    QueueActionState,
    QueueOperation,
    QueueResult,
)


# ---------------------------------------------------------------------------
# Test 1: queue operations expose exactly the required states
# ---------------------------------------------------------------------------

def test_operation_state_has_all_required_values() -> None:
    required = {"queued", "running", "paused", "completed", "failed", "canceled"}
    actual = {s.value for s in OperationState}
    assert actual == required


# ---------------------------------------------------------------------------
# Test 2: failed items retain retry, inspect, skip metadata without blocking
# ---------------------------------------------------------------------------

def test_failed_item_has_retry_skip_inspect_actions() -> None:
    op = QueueOperation(
        state=OperationState.FAILED,
        failure=QueueFailure(short_description="network error", retriable=True),
        continue_on_failure=True,
    )
    actions = op.action_state
    assert actions.can_retry is True
    assert actions.can_skip is True
    assert actions.can_inspect is True


def test_failed_item_with_continue_on_failure_does_not_block() -> None:
    op = QueueOperation(
        state=OperationState.FAILED,
        continue_on_failure=True,
    )
    # continue_on_failure=True means subsequent operations are not blocked
    assert op.continue_on_failure is True


def test_non_retriable_failure_disables_retry() -> None:
    op = QueueOperation(
        state=OperationState.FAILED,
        failure=QueueFailure(short_description="fatal error", retriable=False),
    )
    assert op.action_state.can_retry is False
    assert op.action_state.can_skip is True


def test_running_item_can_be_paused_and_canceled_not_retried() -> None:
    op = QueueOperation(state=OperationState.RUNNING)
    a = op.action_state
    assert a.can_pause is True
    assert a.can_cancel is True
    assert a.can_retry is False
    assert a.can_resume is False


def test_paused_item_can_be_resumed_and_canceled() -> None:
    op = QueueOperation(state=OperationState.PAUSED)
    a = op.action_state
    assert a.can_resume is True
    assert a.can_cancel is True
    assert a.can_pause is False


def test_queued_item_can_only_be_canceled_not_paused_or_resumed() -> None:
    op = QueueOperation(state=OperationState.QUEUED)
    a = op.action_state
    assert a.can_cancel is True
    assert a.can_pause is False
    assert a.can_resume is False


def test_completed_item_has_no_active_transitions() -> None:
    op = QueueOperation(state=OperationState.COMPLETED)
    a = op.action_state
    assert a.can_cancel is False
    assert a.can_pause is False
    assert a.can_retry is False


# ---------------------------------------------------------------------------
# Test 3: profile-apply operations store linked download follow-ups and undo metadata
# ---------------------------------------------------------------------------

def test_profile_apply_operation_can_reference_linked_downloads() -> None:
    download_op = QueueOperation(
        source=OperationSource.DOWNLOADER,
        kind=OperationKind.DOWNLOAD,
        state=OperationState.QUEUED,
    )
    apply_op = QueueOperation(
        source=OperationSource.PROFILE_APPLY,
        kind=OperationKind.PROFILE_APPLY,
        state=OperationState.COMPLETED,
        linked_operation_ids=[download_op.id],
        snapshot_id="snap-001",
        undo_eligible=True,
    )
    assert download_op.id in apply_op.linked_operation_ids
    assert apply_op.snapshot_id == "snap-001"
    assert apply_op.undo_eligible is True
    assert apply_op.action_state.can_undo is True


def test_completed_profile_apply_without_snapshot_is_not_undo_eligible() -> None:
    op = QueueOperation(
        source=OperationSource.PROFILE_APPLY,
        kind=OperationKind.PROFILE_APPLY,
        state=OperationState.COMPLETED,
        undo_eligible=False,
    )
    assert op.action_state.can_undo is False


def test_default_continue_on_failure_is_true() -> None:
    op = QueueOperation()
    assert op.continue_on_failure is True


def test_operation_id_is_unique() -> None:
    ops = [QueueOperation() for _ in range(20)]
    ids = [op.id for op in ops]
    assert len(set(ids)) == 20


def test_operation_source_labels() -> None:
    assert OperationSource.DOWNLOADER.value == "Downloader"
    assert OperationSource.CHECKER.value == "Checker"
    assert OperationSource.PROFILE_APPLY.value == "Profile Apply"
