"""SaveProfileDialog — full-screen dialog for saving the current mod state as a profile.

Replaces the inline save panel from ProfileLibraryDialog.  Supports hundreds of mods
via a live search (debounced 300 ms) and "Select All / None" scoped to visible rows.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.mod_list import ModListStore
from ..core.profiles import Profile, ProfileStore

logger = logging.getLogger(__name__)


class SaveProfileDialog(QDialog):
    """Dialog for saving the current enabled-mod state as a named profile.

    Emits ``profile_saved(profile_id)`` after a successful save so the
    caller can refresh its profile list and pre-select the new entry.
    """

    profile_saved = Signal(str)  # profile_id

    def __init__(
        self,
        mods_folder: str,
        installed_mods: dict,
        profile_store: ProfileStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Current State as Profile")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setModal(True)

        self._mods_folder = mods_folder
        self._installed_mods: dict = installed_mods or {}
        self._profile_store = profile_store

        # Load current enabled state from mod-list.json
        self._current_enabled: dict = {}
        if mods_folder:
            try:
                self._current_enabled = ModListStore(Path(mods_folder)).load()
            except Exception:
                logger.exception("Failed to load mod list from %s", mods_folder)

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self._tree: Optional[QTreeWidget] = None
        self._count_label: Optional[QLabel] = None
        self._search_edit: Optional[QLineEdit] = None
        self._name_edit: Optional[QLineEdit] = None
        self._save_btn: Optional[QPushButton] = None

        self._setup_ui()
        self._populate_tree()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # --- Title ---
        title = QLabel("Save Current State as Profile")
        title.setObjectName("sectionHeader")
        root.addWidget(title)

        subtitle = QLabel(
            "Select the mods to include in this profile. "
            "Enabled mods are pre-checked; disabled mods are unchecked."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("sectionDescription")
        root.addWidget(subtitle)

        # --- Toolbar: search + Select All/None + count badge ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search mods…")
        self._search_edit.setFixedWidth(300)
        self._search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_edit)

        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setFixedWidth(90)
        sel_all_btn.clicked.connect(lambda: self._toggle_visible(True))
        toolbar.addWidget(sel_all_btn)

        sel_none_btn = QPushButton("Select None")
        sel_none_btn.setFixedWidth(90)
        sel_none_btn.clicked.connect(lambda: self._toggle_visible(False))
        toolbar.addWidget(sel_none_btn)

        toolbar.addStretch()

        self._count_label = QLabel("")
        self._count_label.setObjectName("sectionDescription")
        toolbar.addWidget(self._count_label)

        root.addLayout(toolbar)

        # --- Mod tree (checkbox col + display name col) ---
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "Mod"])
        self._tree.header().setStretchLastSection(True)
        self._tree.header().resizeSection(0, 28)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self._tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tree.itemChanged.connect(self._on_item_changed)
        root.addWidget(self._tree, stretch=1)

        # --- Footer: name field + Save + Cancel ---
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Profile name…")
        footer.addWidget(self._name_edit, stretch=1)

        self._save_btn = QPushButton("Save Profile")
        self._save_btn.setObjectName("accentButton")
        self._save_btn.clicked.connect(self._on_save)
        footer.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        if self._tree is None:
            return

        self._tree.blockSignals(True)
        self._tree.clear()

        # Union of installed mod names and mod-list.json entries so mods appear
        # even when mod-list.json is missing/empty (or has entries not on disk).
        all_mod_names = (set(self._installed_mods.keys()) | set(self._current_enabled.keys())) - {"base"}
        sorted_mods = sorted(all_mod_names, key=str.lower)

        for mod_name in sorted_mods:
            # Default enabled: use mod-list.json value, or True for installed mods not listed
            enabled = self._current_enabled.get(mod_name, True)

            # Display title from installed_mods if available
            mod_obj = self._installed_mods.get(mod_name)
            display_title = getattr(mod_obj, "title", None) or mod_name
            if display_title != mod_name:
                display = f"{display_title}  ({mod_name})"
            else:
                display = mod_name

            item = QTreeWidgetItem(["", display])
            item.setData(0, Qt.ItemDataRole.UserRole, mod_name)  # store raw name
            item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemNeverHasChildren
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked,
            )
            self._tree.addTopLevelItem(item)

        self._tree.blockSignals(False)
        self._update_count()

    # ------------------------------------------------------------------
    # Search / filter
    # ------------------------------------------------------------------

    def _on_search_changed(self) -> None:
        self._search_timer.start()

    def _apply_search_filter(self) -> None:
        if self._tree is None or self._search_edit is None:
            return
        query = self._search_edit.text().strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item is None:
                continue
            text = item.text(1).lower()
            raw = (item.data(0, Qt.ItemDataRole.UserRole) or "").lower()
            hidden = bool(query) and query not in text and query not in raw
            item.setHidden(hidden)
        self._update_count()

    # ------------------------------------------------------------------
    # Select All / None (scoped to visible rows)
    # ------------------------------------------------------------------

    def _toggle_visible(self, checked: bool) -> None:
        if self._tree is None:
            return
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and not item.isHidden():
                item.setCheckState(0, state)
        self._tree.blockSignals(False)
        self._update_count()

    # ------------------------------------------------------------------
    # Count badge
    # ------------------------------------------------------------------

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 0:
            self._update_count()

    def _update_count(self) -> None:
        if self._tree is None or self._count_label is None:
            return
        checked = 0
        total = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item is None:
                continue
            total += 1
            if item.checkState(0) == Qt.CheckState.Checked:
                checked += 1
        self._count_label.setText(f"{checked} / {total} selected")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _get_checked_mods(self) -> list[str]:
        """Return all checked mod names regardless of visibility (always includes 'base')."""
        result = ["base"]
        if self._tree is None:
            return result
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.checkState(0) == Qt.CheckState.Checked:
                raw_name = item.data(0, Qt.ItemDataRole.UserRole)
                if raw_name:
                    result.append(raw_name)
        return result

    def _on_save(self) -> None:
        if self._name_edit is None:
            return
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setPlaceholderText("Please enter a name…")
            return
        enabled_mods = self._get_checked_mods()
        try:
            profile = Profile.from_enabled_state(name, enabled_mods)
            self._profile_store.save(profile)
            self.profile_saved.emit(profile.id)
            self.accept()
        except Exception as exc:
            logger.warning("Could not save profile: %s", exc)
