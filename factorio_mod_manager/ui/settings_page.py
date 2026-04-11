"""Centralized Settings page — Phase 3."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..utils.config import config, Config
from .styles import load_and_apply_theme


class SettingsPage(QWidget):
    """Centralized settings page.

    Signals:
        settings_saved — emitted after Save writes to config
        cancel_requested — emitted when Cancel is clicked (host navigates away)
    """

    settings_saved = Signal()
    cancel_requested = Signal()

    _THEME_OPTIONS: list[tuple[str, str]] = [
        ("Dark", "dark"),
        ("Light", "light"),
        ("System", "system"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._original_values: dict[str, Any] = {}
        self._setup_ui()
        # Wire action buttons
        self._browse_btn.clicked.connect(self._on_browse)
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._reset_btn.clicked.connect(self._on_reset)
        # Live theme preview (D-17): immediate visual change on combo change
        self._theme_combo.currentIndexChanged.connect(self._on_theme_preview)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page header zone
        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        page_title = QLabel("Settings")
        page_title.setObjectName("pageTitle")
        header_layout.addWidget(page_title)
        header_layout.addStretch()
        root.addWidget(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(24, 16, 24, 16)
        inner_layout.setSpacing(16)

        # ── Paths section ─────────────────────────────────────────────
        paths_group = QGroupBox("Paths")
        paths_form = QFormLayout(paths_group)
        paths_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        paths_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        mods_row = QWidget()
        mods_row_layout = QHBoxLayout(mods_row)
        mods_row_layout.setContentsMargins(0, 0, 0, 0)
        mods_row_layout.setSpacing(8)
        self._mods_folder_edit = QLineEdit()
        self._mods_folder_edit.setReadOnly(True)
        self._mods_folder_edit.setPlaceholderText("Not set — auto-detected")
        self._browse_btn = QPushButton("Browse\u2026")
        mods_row_layout.addWidget(self._mods_folder_edit, stretch=1)
        mods_row_layout.addWidget(self._browse_btn)
        paths_form.addRow("Mods Folder:", mods_row)
        inner_layout.addWidget(paths_group)

        # ── Behavior section ──────────────────────────────────────────
        behavior_group = QGroupBox("Behavior")
        behavior_form = QFormLayout(behavior_group)
        behavior_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        behavior_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._max_workers_spin = QSpinBox()
        self._max_workers_spin.setRange(1, 16)
        self._max_workers_spin.setSingleStep(1)
        behavior_form.addRow("Max workers:", self._max_workers_spin)

        self._auto_backup_check = QCheckBox("Auto-backup before updates")
        behavior_form.addRow("", self._auto_backup_check)

        self._auto_refresh_check = QCheckBox("Refresh on launch")
        behavior_form.addRow("", self._auto_refresh_check)
        inner_layout.addWidget(behavior_group)

        # ── Appearance section ────────────────────────────────────────
        appearance_group = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._theme_combo = QComboBox()
        for label, _ in self._THEME_OPTIONS:
            self._theme_combo.addItem(label)
        appearance_form.addRow("Theme:", self._theme_combo)
        inner_layout.addWidget(appearance_group)

        # ── Advanced section ──────────────────────────────────────────
        advanced_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout(advanced_group)
        adv_layout.addWidget(QLabel("No advanced settings in this version."))
        inner_layout.addWidget(advanced_group)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        # ── Footer buttons (outside scroll, pinned bottom) ────────────
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 8, 24, 12)
        footer_layout.setSpacing(8)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("accentButton")
        self._reset_btn = QPushButton("Reset to Defaults")
        self._cancel_btn = QPushButton("Cancel")

        footer_layout.addWidget(self._save_btn)
        footer_layout.addWidget(self._reset_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self._cancel_btn)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    # Public API — called by MainWindow
    # ------------------------------------------------------------------

    def load_values(self) -> None:
        """Populate all form controls from current config and snapshot originals."""
        mods_folder = config.get("mods_folder", "") or ""
        theme = config.get("theme", "dark")
        max_workers = config.get("max_workers", 4)
        auto_backup = config.get("auto_backup", True)
        auto_refresh = config.get("auto_refresh", True)

        self._mods_folder_edit.setText(str(mods_folder))

        theme_idx = next(
            (i for i, (_, v) in enumerate(self._THEME_OPTIONS) if v == theme), 0
        )
        self._theme_combo.blockSignals(True)
        self._theme_combo.setCurrentIndex(theme_idx)
        self._theme_combo.blockSignals(False)

        self._max_workers_spin.blockSignals(True)
        self._max_workers_spin.setValue(int(max_workers))
        self._max_workers_spin.blockSignals(False)

        self._auto_backup_check.blockSignals(True)
        self._auto_backup_check.setChecked(bool(auto_backup))
        self._auto_backup_check.blockSignals(False)

        self._auto_refresh_check.blockSignals(True)
        self._auto_refresh_check.setChecked(bool(auto_refresh))
        self._auto_refresh_check.blockSignals(False)

        # Snapshot for unsaved-changes detection
        self._original_values = {
            "mods_folder": mods_folder,
            "theme": theme,
            "max_workers": int(max_workers),
            "auto_backup": bool(auto_backup),
            "auto_refresh": bool(auto_refresh),
        }

    def get_values(self) -> dict[str, Any]:
        """Return current UI field values (not yet persisted)."""
        return {
            "mods_folder": self._mods_folder_edit.text().strip() or None,
            "theme": self._THEME_OPTIONS[self._theme_combo.currentIndex()][1],
            "max_workers": self._max_workers_spin.value(),
            "auto_backup": self._auto_backup_check.isChecked(),
            "auto_refresh": self._auto_refresh_check.isChecked(),
        }

    def has_unsaved_changes(self) -> bool:
        """Return True if any field differs from snapshot taken at load_values()."""
        current = self.get_values()
        for key, original in self._original_values.items():
            if current.get(key) != original:
                return True
        return False

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        """Open folder picker for mods_folder."""
        current = self._mods_folder_edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Factorio Mods Folder",
            current,
        )
        if path:
            self._mods_folder_edit.setText(path)

    def _on_theme_preview(self, index: int) -> None:
        """Apply theme immediately when user changes combo (live preview, D-17)."""
        theme = self._THEME_OPTIONS[index][1]
        load_and_apply_theme(theme)

    def _on_save(self) -> None:
        """Write all field values to config and emit settings_saved."""
        values = self.get_values()
        for key, value in values.items():
            config.set(key, value)
        # Apply theme explicitly on save
        load_and_apply_theme(values["theme"])
        # Update snapshot so has_unsaved_changes() resets to False
        self._original_values = values.copy()
        self.settings_saved.emit()

    def _on_cancel(self) -> None:
        """Revert UI to original values, revert theme, emit cancel_requested."""
        if self._original_values:
            # Revert theme to what it was before this settings session
            original_theme = self._original_values.get("theme", "dark")
            load_and_apply_theme(original_theme)
            # Reload form controls to match original values
            self.load_values()
        self.cancel_requested.emit()

    def _on_reset(self) -> None:
        """Reset all controls to Config.DEFAULTS values (non-destructive for paths)."""
        defaults = Config.DEFAULTS
        default_theme = defaults.get("theme", "dark")

        self._theme_combo.blockSignals(True)
        theme_idx = next(
            (i for i, (_, v) in enumerate(self._THEME_OPTIONS) if v == default_theme), 0
        )
        self._theme_combo.setCurrentIndex(theme_idx)
        self._theme_combo.blockSignals(False)

        self._max_workers_spin.setValue(defaults.get("max_workers", 4))
        self._auto_backup_check.setChecked(defaults.get("auto_backup", True))
        self._auto_refresh_check.setChecked(defaults.get("auto_refresh", True))
        # Do NOT reset mods_folder — user's path must never be wiped by Reset
        # Apply preview of default theme
        load_and_apply_theme(default_theme)
