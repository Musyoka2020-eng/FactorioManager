"""Profile Library Dialog — save current state, apply profiles, and browse presets.

Three top-level actions without nesting:
  1. Save Current as Profile — serialises the current enabled-mod state.
  2. Saved Profiles — apply or delete user-created profiles.
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

from ..core.mod_list import ModListStore
from ..core.profiles import CURATED_PRESETS, Profile, ProfileStore

logger = logging.getLogger(__name__)


class ProfileLibraryDialog(QDialog):
    """Modal dialog for managing and applying mod profiles.

    Emits ``profile_selected(identifier)`` when the user triggers an
    Apply action.  The *identifier* is either a saved ``Profile.name``
    or a ``PresetFamily.value`` string.
    """

    profile_selected = Signal(str)  # profile name or preset family value

    def __init__(self, mods_folder: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileLibraryDialog")
        self.setWindowTitle("Profile Library")
        self.setMinimumWidth(480)
        self.setMinimumHeight(560)
        self.setModal(True)

        self._mods_folder = mods_folder
        self._profile_store = ProfileStore() if not mods_folder else ProfileStore()
        # Load current enabled state for "Save Current" feature
        self._current_enabled: dict = {}
        if mods_folder:
            try:
                self._current_enabled = ModListStore(Path(mods_folder)).load()
            except Exception:
                pass

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
            "Capture the current enabled / disabled state as a named profile."
        )
        save_desc.setWordWrap(True)
        save_desc.setObjectName("sectionDescription")
        save_section_body.addWidget(save_desc)

        save_row = QHBoxLayout()
        self._save_name_edit = QLineEdit()
        self._save_name_edit.setPlaceholderText("Profile name…")
        self._save_btn = QPushButton("Save Profile")
        self._save_btn.clicked.connect(self._on_save_profile)
        save_row.addWidget(self._save_name_edit, stretch=1)
        save_row.addWidget(self._save_btn)
        save_section_body.addLayout(save_row)
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
        self._delete_profile_btn = QPushButton("Delete")
        self._delete_profile_btn.setObjectName("destructiveButton")
        self._delete_profile_btn.setEnabled(False)
        self._delete_profile_btn.clicked.connect(self._on_delete_profile)
        profile_actions.addWidget(self._apply_profile_btn)
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
        presets_grid = QVBoxLayout()

        for seed in CURATED_PRESETS:
            card = self._make_preset_card(seed.family.value, seed.description)
            presets_grid.addWidget(card)

        presets_section.layout().addLayout(presets_grid)
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

    def _refresh_profile_list(self) -> None:
        self._profile_list.clear()
        profiles = self._profile_store.load_all()
        for p in profiles:
            item = QListWidgetItem(p.name)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._profile_list.addItem(item)
        if not profiles:
            item = QListWidgetItem("No profiles saved yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._profile_list.addItem(item)

    def _selected_profile_id(self) -> Optional[str]:
        items = self._profile_list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_profile_selection_changed(self) -> None:
        has_selection = bool(self._profile_list.selectedItems())
        self._apply_profile_btn.setEnabled(has_selection)
        self._delete_profile_btn.setEnabled(has_selection)

    def _on_save_profile(self) -> None:
        name = self._save_name_edit.text().strip()
        if not name:
            self._save_name_edit.setPlaceholderText("Please enter a name…")
            return
        enabled_mods = [n for n, e in self._current_enabled.items() if e]
        try:
            profile = Profile.from_enabled_state(name, enabled_mods)
            self._profile_store.save(profile)
            self._save_name_edit.clear()
            self._refresh_profile_list()
        except Exception as exc:
            logger.warning("Could not save profile: %s", exc)

    def _on_apply_saved_profile(self) -> None:
        pid = self._selected_profile_id()
        if not pid:
            return
        # find profile by id from all profiles
        profile = next((p for p in self._profile_store.load_all() if p.id == pid), None)
        if profile:
            self.profile_selected.emit(profile.name)
            self.accept()

    def _on_delete_profile(self) -> None:
        pid = self._selected_profile_id()
        if pid:
            self._profile_store.delete(pid)
            self._refresh_profile_list()

    def _on_apply_preset(self, family_name: str) -> None:
        self.profile_selected.emit(family_name)
        self.accept()
