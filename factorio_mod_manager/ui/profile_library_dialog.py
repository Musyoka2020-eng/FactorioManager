"""Profile Library Dialog — save current state, apply profiles, and browse presets.

Three top-level actions without nesting:
  1. Save Current as Profile — serialises the current enabled-mod state (with mod checklist).
  2. Saved Profiles — apply, rename, edit mods, or delete user-created profiles.
  3. Starter Presets — apply one of the three locked preset families.

The dialog emits ``profile_selected(identifier)`` so the caller (CheckerTab)
can hand off to the apply-diff flow without owning apply logic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
# QListWidget / QListWidgetItem still used by _ProfileModEditDialog and the profiles list

from ..core.mod_list import ModListStore
from ..core.profiles import CURATED_PRESETS, Profile, ProfileStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# _ProfileModEditDialog — inner dialog for editing a profile's desired mods
# ---------------------------------------------------------------------------

class _ProfileModEditDialog(QDialog):
    """Small dialog that lets the user modify which mods a profile contains."""

    def __init__(
        self,
        profile: Profile,
        all_enabled: dict,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Mods — {profile.name}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(480)
        self.setModal(True)

        self._profile = profile
        self._all_enabled = all_enabled
        self._mod_list: Optional[QListWidget] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        desc = QLabel(
            "Check the mods that should be <b>enabled</b> when this profile is active."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        self._mod_list = QListWidget()
        self._mod_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        desired = set(self._profile.desired_mods)
        all_names = sorted(set(self._all_enabled.keys()) | desired)
        for name in all_names:
            if name == "base":
                continue
            item = QListWidgetItem(name)
            item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked if name in desired else Qt.CheckState.Unchecked
            )
            self._mod_list.addItem(item)

        root.addWidget(self._mod_list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def get_desired_mods(self) -> list:
        """Return the list of checked mod names (always includes 'base')."""
        checked = ["base"]
        if self._mod_list is None:
            return checked
        for i in range(self._mod_list.count()):
            item = self._mod_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(item.text())
        return checked


class ProfileLibraryDialog(QDialog):
    """Modal dialog for managing and applying mod profiles.

    Emits ``profile_selected(identifier)`` when the user triggers an
    Apply action.  The *identifier* is either a saved ``Profile.name``
    or a ``PresetFamily.value`` string.
    """

    profile_selected = Signal(str)  # profile name or preset family value

    def __init__(
        self,
        mods_folder: str = "",
        installed_mods: Optional[dict] = None,
        queue_controller=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileLibraryDialog")
        self.setWindowTitle("Profile Library")
        self.setMinimumWidth(680)
        self.setMinimumHeight(720)
        self.setModal(True)

        self._mods_folder = mods_folder
        self._installed_mods: dict = installed_mods or {}
        self._queue_controller = queue_controller
        self._profile_store = ProfileStore()
        # Load current enabled state for "Save Current" feature
        self._current_enabled: dict = {}
        if mods_folder:
            try:
                self._current_enabled = ModListStore(Path(mods_folder)).load()
            except Exception:
                logger.exception("Failed to load mod list from %s", mods_folder)

        self._setup_ui()
        self._refresh_profile_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(0)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 8)
        content_layout.setSpacing(16)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # ------------------------------------------------------------------
        # Section 1: Save Current as Profile
        # ------------------------------------------------------------------
        save_section = self._make_section("Save Current as Profile")
        save_section_body = QVBoxLayout()

        save_desc = QLabel(
            "Open a full-screen dialog to choose which mods to include "
            "and give the new profile a name."
        )
        save_desc.setWordWrap(True)
        save_desc.setObjectName("sectionDescription")
        save_section_body.addWidget(save_desc)

        open_save_btn = QPushButton("Save Current State as Profile\u2026")
        open_save_btn.setObjectName("accentButton")
        open_save_btn.clicked.connect(self._on_open_save_dialog)
        save_section_body.addWidget(open_save_btn)

        save_section.layout().addLayout(save_section_body)
        content_layout.addWidget(save_section)

        # ------------------------------------------------------------------
        # Section 2: Saved Profiles
        # ------------------------------------------------------------------
        profiles_section = self._make_section("Saved Profiles")
        profiles_body = QVBoxLayout()

        self._profile_list = QListWidget()
        self._profile_list.setMinimumHeight(120)
        self._profile_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        profiles_body.addWidget(self._profile_list)

        profile_actions = QHBoxLayout()
        self._apply_profile_btn = QPushButton("Apply Profile")
        self._apply_profile_btn.setObjectName("accentButton")
        self._apply_profile_btn.setEnabled(False)
        self._apply_profile_btn.clicked.connect(self._on_apply_saved_profile)
        self._rename_profile_btn = QPushButton("Rename")
        self._rename_profile_btn.setEnabled(False)
        self._rename_profile_btn.clicked.connect(self._on_rename_profile)
        self._edit_mods_btn = QPushButton("Edit Mods")
        self._edit_mods_btn.setEnabled(False)
        self._edit_mods_btn.clicked.connect(self._on_edit_mods)
        self._edit_profile_btn = QPushButton("Edit Profile")
        self._edit_profile_btn.setEnabled(False)
        self._edit_profile_btn.clicked.connect(self._on_edit_profile)
        self._delete_profile_btn = QPushButton("Delete")
        self._delete_profile_btn.setObjectName("destructiveButton")
        self._delete_profile_btn.setEnabled(False)
        self._delete_profile_btn.clicked.connect(self._on_delete_profile)
        profile_actions.addWidget(self._apply_profile_btn)
        profile_actions.addWidget(self._rename_profile_btn)
        profile_actions.addWidget(self._edit_mods_btn)
        profile_actions.addWidget(self._edit_profile_btn)
        profile_actions.addWidget(self._delete_profile_btn)
        profile_actions.addStretch()
        profiles_body.addLayout(profile_actions)
        profiles_section.layout().addLayout(profiles_body)
        content_layout.addWidget(profiles_section)

        self._profile_list.itemSelectionChanged.connect(self._on_profile_selection_changed)

        # ------------------------------------------------------------------
        # Section 3: Starter Presets
        # ------------------------------------------------------------------
        presets_section = self._make_section("Starter Presets")
        presets_body = QVBoxLayout()

        coming_soon_lbl = QLabel(
            "ℹ  Curated preset mod lists are coming soon — applying a preset now "
            "will only activate the base game."
        )
        coming_soon_lbl.setWordWrap(True)
        coming_soon_lbl.setObjectName("sectionDescription")
        presets_body.addWidget(coming_soon_lbl)

        for seed in CURATED_PRESETS:
            card = self._make_preset_card(seed.family.value, seed.description)
            presets_body.addWidget(card)

        presets_section.layout().addLayout(presets_body)
        content_layout.addWidget(presets_section)
        content_layout.addStretch()

        # ------------------------------------------------------------------
        # Close button row
        # ------------------------------------------------------------------
        close_row = QHBoxLayout()
        close_row.setContentsMargins(20, 8, 20, 0)
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    # ------------------------------------------------------------------
    # Section / card helpers
    # ------------------------------------------------------------------

    def _make_section(self, title: str) -> QFrame:
        """Create a labeled card frame for a dialog section."""
        frame = QFrame()
        frame.setObjectName("profileLibraryCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        header = QLabel(title)
        header.setObjectName("sectionHeader")
        layout.addWidget(header)
        return frame

    def _make_preset_card(self, family_name: str, description: str) -> QFrame:
        """Create a preset family card with Apply button."""
        card = QFrame()
        card.setObjectName("profileLibraryCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 8, 8)
        card_layout.setSpacing(8)

        text_col = QVBoxLayout()
        name_lbl = QLabel(family_name)
        name_lbl.setObjectName("presetFamilyName")
        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("presetFamilyDesc")
        desc_lbl.setWordWrap(True)
        text_col.addWidget(name_lbl)
        text_col.addWidget(desc_lbl)
        card_layout.addLayout(text_col, stretch=1)

        apply_btn = QPushButton("Apply")
        apply_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        apply_btn.clicked.connect(
            lambda _checked=False, name=family_name: self._on_apply_preset(name)
        )
        card_layout.addWidget(apply_btn)
        return card

    # ------------------------------------------------------------------
    # Profile list helpers
    # ------------------------------------------------------------------

    def _refresh_profile_list(self, select_id: Optional[str] = None) -> None:
        """Reload the saved profiles list, optionally re-selecting by profile id."""
        self._profile_list.clear()
        profiles = self._profile_store.load_all()
        for p in profiles:
            item = QListWidgetItem(p.name)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._profile_list.addItem(item)
            if select_id and p.id == select_id:
                self._profile_list.setCurrentItem(item)
        if not profiles:
            item = QListWidgetItem("No profiles saved yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._profile_list.addItem(item)

    def _selected_profile(self) -> Optional[Profile]:
        """Return the currently selected Profile object, or None."""
        items = self._profile_list.selectedItems()
        if not items:
            return None
        pid = items[0].data(Qt.ItemDataRole.UserRole)
        if not pid:
            return None
        return next((p for p in self._profile_store.load_all() if p.id == pid), None)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_profile_selection_changed(self) -> None:
        has_selection = bool(self._selected_profile())
        self._apply_profile_btn.setEnabled(has_selection)
        self._rename_profile_btn.setEnabled(has_selection)
        self._edit_mods_btn.setEnabled(has_selection)
        self._edit_profile_btn.setEnabled(has_selection)
        self._delete_profile_btn.setEnabled(has_selection)

    def _on_open_save_dialog(self) -> None:
        """Open SaveProfileDialog; refresh profile list on successful save."""
        from .profile_save_dialog import SaveProfileDialog
        dlg = SaveProfileDialog(
            self._mods_folder,
            self._installed_mods,
            self._profile_store,
            parent=self,
        )
        dlg.profile_saved.connect(
            lambda pid: self._refresh_profile_list(select_id=pid)
        )
        dlg.exec()

    def _on_apply_saved_profile(self) -> None:
        profile = self._selected_profile()
        if profile:
            self.profile_selected.emit(profile.id)
            self.accept()

    def _on_rename_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Profile", "New profile name:", text=profile.name
        )
        if not ok or not new_name.strip():
            return
        profile.name = new_name.strip()
        try:
            self._profile_store.save(profile)
            self._refresh_profile_list(select_id=profile.id)
        except Exception as exc:
            logger.warning("Could not rename profile: %s", exc)

    def _on_edit_mods(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        dlg = _ProfileModEditDialog(profile, self._current_enabled, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            profile.desired_mods = dlg.get_desired_mods()
            try:
                self._profile_store.save(profile)
                self._refresh_profile_list(select_id=profile.id)
            except Exception as exc:
                logger.warning("Could not save edited profile: %s", exc)

    def _on_delete_profile(self) -> None:
        profile = self._selected_profile()
        if profile:
            self._profile_store.delete(profile.id)
            self._refresh_profile_list()

    def _on_edit_profile(self) -> None:
        """Open the full ProfileEditorDialog for the selected profile."""
        profile = self._selected_profile()
        if not profile:
            return
        from .profile_editor_dialog import ProfileEditorDialog
        dlg = ProfileEditorDialog(
            profile,
            self._installed_mods,
            self._profile_store,
            queue_controller=self._queue_controller,
            parent=self,
        )
        # Forward any download requests up to the parent (CheckerTab)
        dlg.download_requested.connect(
            lambda names: self.parent() and hasattr(self.parent(), '_on_profile_download_requested')
            and self.parent()._on_profile_download_requested(names)  # type: ignore[union-attr]
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_profile_list(select_id=profile.id)

    def _on_apply_preset(self, family_name: str) -> None:
        self.profile_selected.emit(family_name)
        self.accept()
