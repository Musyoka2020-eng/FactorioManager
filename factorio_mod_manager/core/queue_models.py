"""Shared queue operation enums and dataclasses for Phase 4 workflows.

All queue-backed work (downloads, updates, profile apply) shares these
typed contracts.  Later plans build on these types instead of introducing
ad-hoc dict payloads.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class OperationSource(str, Enum):
    """Which workflow originated the operation."""
    DOWNLOADER = "Downloader"
    CHECKER = "Checker"
    PROFILE_APPLY = "Profile Apply"


class OperationKind(str, Enum):
    """What kind of action the operation performs."""
    DOWNLOAD = "download"
    UPDATE = "update"
    PROFILE_APPLY = "profile_apply"
    ENABLE_TOGGLE = "enable_toggle"
    RESOLVE = "resolve"


class OperationState(str, Enum):
    """Current lifecycle state of a queue operation."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# ---------------------------------------------------------------------------
# Failure and action metadata
# ---------------------------------------------------------------------------


@dataclass
class QueueFailure:
    """Failure details attached to a failed operation."""

    short_description: str
    # Longer plain-text explanation shown in the inspect view
    detail: str = ""
    # Whether the operation is eligible for retry
    retriable: bool = True
    # Exception type name for diagnostics (never rendered as rich text)
    exception_type: Optional[str] = None


@dataclass
class QueueActionState:
    """Action enable/disable flags for the queue item's current state."""

    can_pause: bool = False
    can_resume: bool = False
    can_cancel: bool = False
    can_retry: bool = False
    can_skip: bool = False
    can_inspect: bool = False
    can_undo: bool = False
    can_move_up: bool = False
    can_move_down: bool = False


# ---------------------------------------------------------------------------
# Core queue operation dataclass
# ---------------------------------------------------------------------------


@dataclass
class QueueOperation:
    """One unit of work managed by the shared queue controller.

    Immutable ID, mutable state fields updated by the controller.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: OperationSource = OperationSource.DOWNLOADER
    kind: OperationKind = OperationKind.DOWNLOAD
    state: OperationState = OperationState.QUEUED

    # Human-readable label shown in queue strips and drawer cards
    label: str = ""

    # Whether a failed item should block subsequent queued items.
    # Default is False (continue-on-failure) per D-04.
    continue_on_failure: bool = True

    # Progress 0-100, or None if not applicable
    progress: Optional[int] = None

    # Failure details (populated when state == FAILED)
    failure: Optional[QueueFailure] = None

    # Undo metadata: only populated for completed profile-apply operations
    snapshot_id: Optional[str] = None
    undo_eligible: bool = False

    # Linked follow-up operation IDs (e.g. missing-mod downloads for profile apply)
    linked_operation_ids: List[str] = field(default_factory=list)

    # Arbitrary inspect payload stored as plain-text dict (never rendered as HTML)
    inspect_payload: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------

    @property
    def action_state(self) -> QueueActionState:
        """Derive which actions are currently legal for this operation."""
        s = self.state
        return QueueActionState(
            can_pause=s == OperationState.RUNNING,
            can_resume=s == OperationState.PAUSED,
            can_cancel=s in (OperationState.QUEUED, OperationState.RUNNING, OperationState.PAUSED),
            can_retry=s == OperationState.FAILED and (self.failure is None or self.failure.retriable),
            can_skip=s == OperationState.FAILED,
            can_inspect=s in (OperationState.FAILED, OperationState.COMPLETED),
            can_undo=s == OperationState.COMPLETED and self.undo_eligible,
        )

    @property
    def is_active(self) -> bool:
        """True if the operation is currently doing work or waiting to do so."""
        return self.state in (
            OperationState.QUEUED,
            OperationState.RUNNING,
            OperationState.PAUSED,
        )

    @property
    def is_terminal(self) -> bool:
        """True if the operation has reached a final state."""
        return self.state in (OperationState.COMPLETED, OperationState.CANCELED)


# ---------------------------------------------------------------------------
# Result record
# ---------------------------------------------------------------------------


@dataclass
class QueueResult:
    """Outcome record written after an operation reaches a terminal state."""

    operation_id: str
    state: OperationState
    snapshot_id: Optional[str] = None
    failure: Optional[QueueFailure] = None
    linked_operation_ids: List[str] = field(default_factory=list)
