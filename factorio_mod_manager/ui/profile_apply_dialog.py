"""Profile Apply Dialog — interactive diff review before confirming a profile apply.

Two-pane layout (≥900 px):
  Left rail  — Profile title, live action count summary, filter controls, action buttons.
  Right pane — Interactive diff tree (checkboxes for enable items, download buttons).

``ProfileApplyDialog.accepted_diff()`` returns the filtered diff after the user
has toggled any items.  The caller should use this diff (not the original) when
creating the apply job.

``ProfileApplyDialog.download_requested`` is emitted with a list of mod names
when the user confirms a download for a DOWNLOAD-action item.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.profiles import DiffAction, ProfileDiff, ProfileDiffItem, Profile, ProfileStore

# -------------------------------------------------------------------------
# Colour map for diff-action chips
# -------------------------------------------------------------------------

_ACTION_COLOUR: dict[DiffAction, str] = {
    DiffAction.ADD: "#4caf50",
    DiffAction.REMOVE: "#f44336",
    DiffAction.ENABLE: "#2196f3",
    DiffAction.DISABLE: "#ff9800",
    DiffAction.DOWNLOAD: "#9c27b0",
}

_ACTION_LABEL: dict[DiffAction, str] = {
    DiffAction.ADD: "Enable",
    DiffAction.REMOVE: "Disable",
    DiffAction.ENABLE: "Enable",
    DiffAction.DISABLE: "Disable",
    DiffAction.DOWNLOAD: "Download",
}

# Actions whose items can be toggled by the user (enable/add can be skipped)
_TOGGLEABLE = {DiffAction.ENABLE, DiffAction.ADD}


class ProfileApplyDialog(QDialog):
    """Interactive confirmation dialog for a profile apply operation.

    Parameters
    ----------
    diff:
        Pre-computed diff that will be applied.
    profile:
        The Profile object being applied (modified in-place on accept to update
        ``disabled_in_profile``).
    profile_store:
        Store used to persist the profile after user edits disabled_in_profile.
    parent:
        Parent widget (for modal centering).
    """

    # Emitted when the user requests a download for a DOWNLOAD-action item.
    # Payload: list of mod names to enqueue.
    download_requested = Signal(list)

    def __init__(
        self,
        diff: ProfileDiff,
        profile: Profile,
        profile_store: ProfileStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._diff = diff
        self._profile = profile
        self._profile_store = profile_store

        # Working copy of which toggleable items are currently "skipped" (unchecked)
        self._unchecked: set[str] = set()

        # Map mod_name -> chip label widget so we can update counts live
        self._count_chips: Dict[str, QLabel] = {}

        self.setObjectName("profileApplyDialog")
        self.setWindowTitle(f"Apply Profile: {diff.profile_name}")
        self.setMinimumWidth(900)
        self.setMinimumHeight(560)
        self.setModal(True)

        self._build_ui()
        self._populate_tree()

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

        sub = QLabel("Check or uncheck mods before applying.")
        sub.setObjectName("applyProfileSub")
        sub.setWordWrap(True)
        left_layout.addWidget(sub)

        left_layout.addSpacing(12)

        # Summary counts (kept as live-updating chips)
        self._enable_chip = self._make_count_chip(
            left_layout, "Enable",
            self._diff.enable_count + self._diff.add_count,
            "#4caf50",
        )
        self._disable_chip = self._make_count_chip(
            left_layout, "Disable",
            self._diff.disable_count + self._diff.remove_count,
            "#f44336",
        )
        self._download_chip = self._make_count_chip(
            left_layout, "Download",
            self._diff.download_count,
            "#9c27b0",
        )

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
        self._confirm_btn.clicked.connect(self._on_confirm)
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

        # ---- Right pane (diff tree) ----------------------------------
        right = QWidget()
        right.setObjectName("applyDialogRight")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        list_label = QLabel("Mods to change  (uncheck Enable items to skip them)")
        list_label.setObjectName("diffListLabel")
        right_layout.addWidget(list_label)

        self._tree = QTreeWidget()
        self._tree.setObjectName("diffTree")
        self._tree.setAlternatingRowColors(True)
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(2)
        self._tree.setColumnWidth(0, 260)
        self._tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(0)
        self._tree.itemChanged.connect(self._on_item_toggled)
        right_layout.addWidget(self._tree)

        root.addWidget(right)

    def _make_count_chip(
        self, layout: QVBoxLayout, label_text: str, count: int, colour: str
    ) -> QLabel:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        chip = QLabel(str(count))
        chip.setObjectName("diffCountChip")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setFixedSize(36, 22)
        chip.setStyleSheet(
            f"background:{colour}; color:#fff; border-radius:4px; font-weight:600;"
        )
        lbl = QLabel(label_text)
        lbl.setObjectName("diffCountLabel")
        row_layout.addWidget(chip)
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        layout.addWidget(row)
        return chip

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self, filter_id: int = 0) -> None:
        """Rebuild the diff tree, optionally filtered."""
        # Disconnect during bulk insert to avoid spurious itemChanged signals
        self._tree.itemChanged.disconnect(self._on_item_toggled)
        self._tree.clear()

        for diff_item in self._diff.items:
            if filter_id == 1 and diff_item.action != DiffAction.DOWNLOAD:
                continue
            if filter_id == 2 and diff_item.action == DiffAction.DOWNLOAD:
                continue

            colour = _ACTION_COLOUR.get(diff_item.action, "#888")
            action_text = _ACTION_LABEL.get(diff_item.action, diff_item.action.value)

            tree_item = QTreeWidgetItem()
            tree_item.setData(0, Qt.ItemDataRole.UserRole, diff_item.mod_name)
            tree_item.setData(1, Qt.ItemDataRole.UserRole, diff_item.action)

            if diff_item.action in _TOGGLEABLE:
                # Checkbox column
                checked = diff_item.mod_name not in self._unchecked
                tree_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                tree_item.setCheckState(
                    0,
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked,
                )
                tree_item.setText(0, diff_item.mod_name)
                # Action chip as text in column 1
                tree_item.setText(1, f"[{action_text}]")
                from PySide6.QtGui import QColor
                tree_item.setForeground(1, QColor(colour))
            elif diff_item.action == DiffAction.DOWNLOAD:
                tree_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                tree_item.setText(0, diff_item.mod_name)
                # Download button in column 1 via setItemWidget
                dl_btn = QPushButton("Add to Queue")
                dl_btn.setFixedHeight(22)
                dl_btn.setObjectName("downloadChipButton")
                dl_btn.setStyleSheet(
                    f"background:{colour}; color:#fff; border-radius:3px; font-size:11px;"
                    "padding:0 6px; border:none;"
                )
                mod_name = diff_item.mod_name
                dl_btn.clicked.connect(lambda _=False, n=mod_name: self._on_download_click(n))
                self._tree.addTopLevelItem(tree_item)
                self._tree.setItemWidget(tree_item, 1, dl_btn)
                # Skip the generic addTopLevelItem below
                continue
            else:
                # DISABLE / REMOVE — read-only
                tree_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                tree_item.setText(0, diff_item.mod_name)
                tree_item.setText(1, f"[{action_text}]")
                from PySide6.QtGui import QColor
                tree_item.setForeground(1, QColor(colour))

            self._tree.addTopLevelItem(tree_item)

        self._tree.itemChanged.connect(self._on_item_toggled)

    # ------------------------------------------------------------------
    # Interaction handlers
    # ------------------------------------------------------------------

    def _on_item_toggled(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        mod_name = item.data(0, Qt.ItemDataRole.UserRole)
        if mod_name is None:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self._unchecked.discard(mod_name)
        else:
            self._unchecked.add(mod_name)
        self._refresh_enable_chip()

    def _refresh_enable_chip(self) -> None:
        """Update the Enable count chip to reflect current checkbox state."""
        base_enable = self._diff.enable_count + self._diff.add_count
        skipped = sum(
            1 for item in self._diff.items
            if item.action in _TOGGLEABLE and item.mod_name in self._unchecked
        )
        self._enable_chip.setText(str(base_enable - skipped))

    def _apply_filter(self, filter_id: int) -> None:
        self._populate_tree(filter_id)

    def _on_download_click(self, mod_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Download Mod",
            f"Add <b>{mod_name}</b> and its required dependencies to the download queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.download_requested.emit([mod_name])

    def _on_confirm(self) -> None:
        # Persist the user's toggles back into the profile's disabled_in_profile
        currently_disabled = set(self._profile.disabled_in_profile)
        for diff_item in self._diff.items:
            if diff_item.action not in _TOGGLEABLE:
                continue
            if diff_item.mod_name in self._unchecked:
                currently_disabled.add(diff_item.mod_name)
            else:
                currently_disabled.discard(diff_item.mod_name)
        self._profile.disabled_in_profile = sorted(currently_disabled)
        try:
            self._profile_store.save(self._profile)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Could not save profile changes: {exc}\n\nThe profile apply will not proceed.",
            )
            return
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def accepted_diff(self) -> ProfileDiff:
        """Return the diff with user-unchecked ENABLE/ADD items removed.

        Call this after ``exec()`` returns ``Accepted`` to get the actual
        diff the apply job should execute.
        """
        effective: List[ProfileDiffItem] = [
            item for item in self._diff.items
            if not (item.action in _TOGGLEABLE and item.mod_name in self._unchecked)
        ]
        return ProfileDiff(
            profile_id=self._diff.profile_id,
            profile_name=self._diff.profile_name,
            items=effective,
        )
