"""Profile Apply Dialog — shows the diff before confirming a profile apply.

Two-pane layout (≥900 px):
  Left rail  — Profile title, action count summary, optional filter controls.
  Right pane — Scrollable diff list with color-coded action chips.

Emits no signals; caller reads ``dialog.result()`` after ``exec()``.
Caller must pass a pre-computed :class:`~factorio_mod_manager.core.profiles.ProfileDiff`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.profiles import DiffAction, ProfileDiff

# -------------------------------------------------------------------------
# Colour map for diff-action chips
# -------------------------------------------------------------------------

_ACTION_COLOUR: dict[DiffAction, str] = {
    DiffAction.ADD: "#4caf50",       # green  — added / re-enabled from enabled-list
    DiffAction.REMOVE: "#f44336",    # red    — removed / disabled
    DiffAction.ENABLE: "#2196f3",    # blue   — existing mod re-enabled
    DiffAction.DISABLE: "#ff9800",   # amber  — existing mod disabled
    DiffAction.DOWNLOAD: "#9c27b0",  # purple — new download needed
}

_ACTION_LABEL: dict[DiffAction, str] = {
    DiffAction.ADD: "Enable",
    DiffAction.REMOVE: "Disable",
    DiffAction.ENABLE: "Enable",
    DiffAction.DISABLE: "Disable",
    DiffAction.DOWNLOAD: "Download",
}


class ProfileApplyDialog(QDialog):
    """Confirmation dialog for a profile apply operation.

    Parameters
    ----------
    diff:
        Pre-computed diff that will be applied.
    parent:
        Parent widget (for modal centering).
    """

    def __init__(self, diff: ProfileDiff, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._diff = diff

        self.setObjectName("profileApplyDialog")
        self.setWindowTitle(f"Apply Profile: {diff.profile_name}")
        self.setMinimumWidth(900)
        self.setMinimumHeight(520)
        self.setModal(True)

        self._build_ui()
        self._populate_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Left rail -----------------------------------------------
        left = QWidget()
        left.setObjectName("applyDialogRail")
        left.setFixedWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 20, 16, 20)
        left_layout.setSpacing(8)

        title = QLabel(f"<b>{self._diff.profile_name}</b>")
        title.setObjectName("applyProfileTitle")
        title.setWordWrap(True)
        left_layout.addWidget(title)

        sub = QLabel("Review changes before applying.")
        sub.setObjectName("applyProfileSub")
        sub.setWordWrap(True)
        left_layout.addWidget(sub)

        left_layout.addSpacing(12)

        # Summary counts
        counts: list[tuple[str, int, str]] = [
            ("Enable", self._diff.enable_count + self._diff.add_count, "#4caf50"),
            ("Disable", self._diff.disable_count + self._diff.remove_count, "#f44336"),
            ("Download", self._diff.download_count, "#9c27b0"),
        ]
        for label, count, colour in counts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            chip = QLabel(str(count))
            chip.setObjectName("diffCountChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setFixedSize(32, 22)
            chip.setStyleSheet(
                f"background:{colour}; color:#fff; border-radius:4px; font-weight:600;"
            )
            lbl = QLabel(label)
            lbl.setObjectName("diffCountLabel")
            row_layout.addWidget(chip)
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            left_layout.addWidget(row)

        left_layout.addSpacing(16)

        # Filter radio buttons
        filter_label = QLabel("Show:")
        filter_label.setObjectName("filterLabel")
        left_layout.addWidget(filter_label)

        self._filter_group = QButtonGroup(self)
        filter_all = QRadioButton("All changes")
        filter_all.setChecked(True)
        filter_dl = QRadioButton("Downloads only")
        filter_local = QRadioButton("Local changes only")

        for idx, btn in enumerate((filter_all, filter_dl, filter_local)):
            self._filter_group.addButton(btn, idx)
            left_layout.addWidget(btn)

        self._filter_group.idClicked.connect(self._apply_filter)

        left_layout.addStretch()

        # Action buttons
        self._confirm_btn = QPushButton("Confirm Apply")
        self._confirm_btn.setObjectName("accentButton")
        self._confirm_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.clicked.connect(self.reject)
        left_layout.addWidget(self._confirm_btn)
        left_layout.addWidget(cancel_btn)

        root.addWidget(left)

        # ---- Divider -------------------------------------------------
        divider = QWidget()
        divider.setFixedWidth(1)
        divider.setObjectName("applyDialogDivider")
        root.addWidget(divider)

        # ---- Right pane (diff list) ----------------------------------
        right = QWidget()
        right.setObjectName("applyDialogRight")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        list_label = QLabel("Mods to change")
        list_label.setObjectName("diffListLabel")
        right_layout.addWidget(list_label)

        self._list = QListWidget()
        self._list.setObjectName("diffList")
        self._list.setAlternatingRowColors(True)
        self._list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout.addWidget(self._list)

        root.addWidget(right)

    # ------------------------------------------------------------------
    # List population
    # ------------------------------------------------------------------

    def _populate_list(self, filter_id: int = 0) -> None:
        """Populate the diff list widget, optionally filtered."""
        self._list.clear()
        for item in self._diff.items:
            if filter_id == 1 and item.action != DiffAction.DOWNLOAD:
                continue
            if filter_id == 2 and item.action == DiffAction.DOWNLOAD:
                continue

            colour = _ACTION_COLOUR.get(item.action, "#888")
            action_text = _ACTION_LABEL.get(item.action, item.action.value)
            text = f"[{action_text}]  {item.mod_name}"

            row = QListWidgetItem(text)
            row.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(colour)
            )
            self._list.addItem(row)

    def _apply_filter(self, filter_id: int) -> None:
        self._populate_list(filter_id)
