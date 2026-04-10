"""Checker tab UI — Qt implementation."""
from __future__ import annotations

import html as html_lib
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import ModChecker, Mod, ModStatus
from ..utils import config, format_file_size, is_online
from .widgets import NotificationManager
from .checker_logic import CheckerLogic
from .checker_presenter import CheckerPresenter


# ---------------------------------------------------------------------------
# Worker: ScanWorker
# ---------------------------------------------------------------------------

class ScanWorker(QThread):
    """Runs CheckerLogic.scan_mods() in a background thread."""

    mods_loaded = Signal(object)    # Dict[str, Mod] on success
    log_message = Signal(str, str)  # (message, level_name)
    error = Signal(str)

    def __init__(self, checker_logic: CheckerLogic, parent=None):
        super().__init__(parent)
        self._logic = checker_logic

    def run(self):
        try:
            mods = self._logic.scan_mods()
            self.mods_loaded.emit(mods)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: UpdateCheckWorker
# ---------------------------------------------------------------------------

class UpdateCheckWorker(QThread):
    """Runs CheckerLogic.check_updates() in a background thread."""

    check_complete = Signal(object, bool)  # (outdated_mods, was_refreshed)
    log_message = Signal(str, str)
    error = Signal(str)

    def __init__(self, checker_logic: CheckerLogic, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._logic = checker_logic
        self._force_refresh = force_refresh

    def run(self):
        try:
            outdated, was_refreshed = self._logic.check_updates(
                force_refresh=self._force_refresh
            )
            self.check_complete.emit(outdated, was_refreshed)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: UpdateSelectedWorker
# ---------------------------------------------------------------------------

class UpdateSelectedWorker(QThread):
    """Runs CheckerLogic.update_mods() in a background thread."""

    update_complete = Signal(list, list)  # (successful, failed)
    log_message = Signal(str, str)
    error = Signal(str)

    def __init__(self, checker_logic: CheckerLogic, mod_names: List[str], parent=None):
        super().__init__(parent)
        self._logic = checker_logic
        self._mod_names = list(mod_names)

    def run(self):
        try:
            successful, failed = self._logic.update_mods(self._mod_names)
            self.update_complete.emit(successful, failed)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# CheckerTab — main QWidget
# ---------------------------------------------------------------------------

_LEVEL_COLORS: Dict[str, str] = {
    "DEBUG":    "#b0b0b0",
    "INFO":     "#e0e0e0",
    "WARNING":  "#ffad00",
    "ERROR":    "#d13438",
    "CRITICAL": "#d13438",
    "SUCCESS":  "#4ec952",
}

_STATUS_COLORS: Dict[ModStatus, tuple] = {
    ModStatus.UP_TO_DATE: ("✓ Up to date",  "#4ec952"),
    ModStatus.OUTDATED:   ("⬆️ Outdated",    "#ffad00"),
    ModStatus.UNKNOWN:    ("❓ Unknown",     "#b0b0b0"),
    ModStatus.ERROR:      ("✗ Error",       "#d13438"),
}


class CheckerTab(QWidget):
    """Qt UI for mod checker / updater."""

    _log_signal = Signal(str, str)   # thread-safe bridge for op-log writes

    def __init__(self, logger=None, status_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logger or logging.getLogger(__name__)
        self.status_manager = status_manager
        self.notification_manager: Optional[NotificationManager] = None

        self._first_show = True          # auto-scan guard
        self._mods: Dict[str, Mod] = {}
        self._selected_mods: set = set()
        self._current_filter = "all"
        self._current_sort = "name"
        self._search_query = ""
        self._active_worker = None       # prevents GC before signal delivery

        self._checker: Optional[ModChecker] = None
        self._logic: Optional[CheckerLogic] = None
        self._presenter = CheckerPresenter()

        self._setup_ui()
        self._restore_config()
        self._log_signal.connect(self._append_op_log)

    # ------------------------------------------------------------------
    # NotificationManager interface
    # ------------------------------------------------------------------

    def set_notification_manager(self, manager: NotificationManager) -> None:
        self.notification_manager = manager

    def _notify(self, message, notif_type="info", duration_ms=4000, actions=None):
        if self.notification_manager is not None:
            self.notification_manager.show(
                message, notif_type=notif_type, duration_ms=duration_ms, actions=actions
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Main splitter: left | center | right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ----- LEFT SIDEBAR (220 px fixed) -----
        left_widget = QWidget()
        left_widget.setFixedWidth(220)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        # Folder row
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("Mods folder…")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse)
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(browse_btn)
        left_layout.addLayout(folder_row)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #4ec952; font-size: 11px;")
        left_layout.addWidget(self.status_label)

        # Button stack
        self.scan_btn       = QPushButton("🔍 Scan")
        self.check_btn      = QPushButton("⬆️ Check Updates")
        self.update_sel_btn = QPushButton("📥 Update Selected")
        self.update_all_btn = QPushButton("Update All")
        self.delete_btn     = QPushButton("🗑️ Delete")
        self.backup_btn     = QPushButton("💾 Backup")
        self.clean_btn      = QPushButton("🧹 Clean Backups")
        self.details_btn    = QPushButton("ℹ️ View Details")

        self.delete_btn.setObjectName("destructiveButton")

        for btn in (
            self.scan_btn, self.check_btn, self.update_sel_btn, self.update_all_btn,
            self.delete_btn, self.backup_btn, self.clean_btn, self.details_btn,
        ):
            left_layout.addWidget(btn)

        left_layout.addStretch()

        self.scan_btn.clicked.connect(self._on_scan)
        self.check_btn.clicked.connect(self._on_check_updates)
        self.update_sel_btn.clicked.connect(self._on_update_selected)
        self.update_all_btn.clicked.connect(self._on_update_all)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.backup_btn.clicked.connect(self._on_backup)
        self.clean_btn.clicked.connect(self._on_clean_backups_clicked)
        self.details_btn.clicked.connect(self._on_view_details)

        # ----- CENTER: QTableWidget -----
        self.mod_table = QTableWidget()
        self.mod_table.setColumnCount(6)
        self.mod_table.setHorizontalHeaderLabels(
            ["✔", "Name", "Status", "Version", "Author", "Downloads"]
        )
        self.mod_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mod_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.mod_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.mod_table.setColumnWidth(0, 30)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.setAlternatingRowColors(True)

        # ----- RIGHT SIDEBAR (280 px fixed) -----
        right_widget = QWidget()
        right_widget.setFixedWidth(280)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_vbox = QVBoxLayout(stats_group)
        self.stat_total     = QLabel("Total: 0 mods")
        self.stat_uptodate  = QLabel("Up to date: 0")
        self.stat_outdated  = QLabel("Outdated: 0")
        self.stat_unknown   = QLabel("Unknown: 0")
        self.stat_downloads = QLabel("Downloads: 0")
        for lbl in (
            self.stat_total, self.stat_uptodate, self.stat_outdated,
            self.stat_unknown, self.stat_downloads,
        ):
            lbl.setStyleSheet("font-size: 11px;")
            stats_vbox.addWidget(lbl)
        right_layout.addWidget(stats_group)

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search mods…")
        self.search_edit.textChanged.connect(self._on_search_changed)
        right_layout.addWidget(self.search_edit)

        # Status filter buttons
        filter_group = QGroupBox("Filter")
        filter_vbox = QVBoxLayout(filter_group)
        self._filter_btns: Dict[str, QPushButton] = {}
        for label, key in (("All", "all"), ("Outdated", "outdated"),
                            ("Up to Date", "up_to_date"), ("Selected", "selected")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "all")
            btn.clicked.connect(lambda checked, k=key: self._on_filter_changed(k))
            self._filter_btns[key] = btn
            filter_vbox.addWidget(btn)
        right_layout.addWidget(filter_group)

        # Sort radio buttons
        sort_group = QGroupBox("Sort by")
        sort_vbox = QVBoxLayout(sort_group)
        self._sort_radios: Dict[str, QRadioButton] = {}
        sort_btn_group = QButtonGroup(sort_group)
        for label, key in (("Name", "name"), ("Version", "version"),
                            ("Downloads", "downloads"), ("Date", "date")):
            radio = QRadioButton(label)
            radio.setChecked(key == "name")
            radio.toggled.connect(lambda checked, k=key: self._on_sort_changed(k) if checked else None)
            self._sort_radios[key] = radio
            sort_btn_group.addButton(radio)
            sort_vbox.addWidget(radio)
        right_layout.addWidget(sort_group)
        right_layout.addStretch()

        # Add panes to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(self.mod_table)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        # Operation log
        self.op_log = QTextEdit()
        self.op_log.setReadOnly(True)
        self.op_log.setFixedHeight(120)
        self.op_log.setFont(QFont("Cascadia Code", 9))
        self.op_log.setPlaceholderText("Operation log…")
        root.addWidget(self.op_log)

        # Initial button state
        self._update_button_states()

    def _restore_config(self):
        saved = config.get("mods_folder", "")
        if saved:
            self.folder_edit.setText(str(saved))

    # ------------------------------------------------------------------
    # showEvent — auto-scan on first tab visit
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(3000, self._auto_scan)

    def _auto_scan(self):
        folder = self.folder_edit.text().strip()
        if folder:
            self._on_scan()

    # ------------------------------------------------------------------
    # Logic layer helpers
    # ------------------------------------------------------------------

    def _ensure_logic(self) -> bool:
        """Create CheckerLogic if folder is set. Returns True if ready."""
        folder = self.folder_edit.text().strip()
        if not folder:
            self._notify("Please select a mods folder first.", "warning")
            return False
        if self._checker is None or str(self._checker.mods_folder) != folder:
            self._checker = ModChecker(folder)
            self._logic = CheckerLogic(
                self._checker,
                lambda msg, level="INFO": self._log_signal.emit(msg, level),
            )
        return True

    # ------------------------------------------------------------------
    # Table & statistics
    # ------------------------------------------------------------------

    def _populate_table(self, mods: Dict[str, Mod]):
        """Rebuild QTableWidget from current mods dict with active filter/sort."""
        filtered = self._presenter.filter_mods(
            mods,
            search_query=self._search_query,
            filter_mode=self._current_filter,
            selected_mods=self._selected_mods,
            sort_by=self._current_sort,
        )

        self.mod_table.setRowCount(0)
        self.mod_table.setRowCount(len(filtered))

        for row, (mod_name, mod) in enumerate(filtered):
            # Col 0: checkbox
            chk = QCheckBox()
            chk.setChecked(mod_name in self._selected_mods)
            chk.stateChanged.connect(
                lambda state, name=mod_name: self._on_checkbox_changed(name, state)
            )
            chk_cell = QWidget()
            chk_layout = QHBoxLayout(chk_cell)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.mod_table.setCellWidget(row, 0, chk_cell)

            # Col 1: name
            name_item = QTableWidgetItem(mod_name)
            name_item.setData(Qt.ItemDataRole.UserRole, mod_name)
            self.mod_table.setItem(row, 1, name_item)

            # Col 2: status
            status_text, color = _STATUS_COLORS.get(
                mod.status, ("❓ Unknown", "#b0b0b0")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            self.mod_table.setItem(row, 2, status_item)

            # Col 3: version
            installed = mod.version or "?"
            latest = mod.latest_version or "?"
            version_text = f"{installed} → {latest}" if mod.status == ModStatus.OUTDATED else installed
            self.mod_table.setItem(row, 3, QTableWidgetItem(version_text))

            # Col 4: author
            self.mod_table.setItem(row, 4, QTableWidgetItem(mod.author or ""))

            # Col 5: downloads
            self.mod_table.setItem(row, 5, QTableWidgetItem(str(mod.downloads or "")))

        self.mod_table.scrollToTop()

    def _update_statistics(self, mods: Dict[str, Mod]):
        stats = self._presenter.get_statistics(mods)
        self.stat_total.setText(f"Total: {stats.get('total', 0)} mods")
        self.stat_uptodate.setText(f"Up to date: {stats.get('up_to_date', 0)}")
        self.stat_outdated.setText(f"Outdated: {stats.get('outdated', 0)}")
        self.stat_unknown.setText(f"Unknown: {stats.get('unknown', 0)}")
        dl = sum(m.downloads for m in mods.values() if m.downloads)
        self.stat_downloads.setText(f"Downloads: {dl:,}")

    def _update_button_states(self):
        has_mods = len(self._mods) > 0
        has_selection = len(self._selected_mods) > 0
        one_selected = len(self._selected_mods) == 1
        self.update_sel_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.backup_btn.setEnabled(has_selection)
        self.details_btn.setEnabled(one_selected)
        self.check_btn.setEnabled(has_mods)
        self.update_all_btn.setEnabled(has_mods)

    # ------------------------------------------------------------------
    # Filter / sort handlers
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        self._search_query = text
        self._populate_table(self._mods)

    def _on_filter_changed(self, key: str):
        self._current_filter = key
        # Uncheck other filter buttons
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == key)
        self._populate_table(self._mods)

    def _on_sort_changed(self, key: str):
        self._current_sort = key
        self._populate_table(self._mods)

    def _on_checkbox_changed(self, mod_name: str, state: int):
        if state == Qt.CheckState.Checked.value:
            self._selected_mods.add(mod_name)
        else:
            self._selected_mods.discard(mod_name)
        self._update_button_states()

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Factorio Mods Folder",
            self.folder_edit.text() or str(Path.home()),
        )
        if path:
            self.folder_edit.setText(path)
            config.set("mods_folder", path)
            # Reset checker so it re-initialises with new folder
            self._checker = None
            self._logic = None

    # ------------------------------------------------------------------
    # Operation log
    # ------------------------------------------------------------------

    def _append_op_log(self, message: str, level: str = "INFO"):
        """Append HTML-escaped, color-coded line to operation log."""
        color = _LEVEL_COLORS.get(level.upper(), "#e0e0e0")
        safe = html_lib.escape(message)
        self.op_log.append(f'<span style="color:{color};">{safe}</span>')
        sb = self.op_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Worker result slots
    # ------------------------------------------------------------------

    def _set_busy(self, label: str):
        self.status_label.setText(label)
        self.status_label.setStyleSheet("color: #0078d4; font-size: 11px;")
        self.scan_btn.setEnabled(False)

    def _set_idle(self, label: str = "Ready", color: str = "#4ec952"):
        self.status_label.setText(label)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.scan_btn.setEnabled(True)
        self._active_worker = None
        self._update_button_states()

    @Slot(object)
    def _on_mods_loaded(self, mods: dict):
        self._mods = mods
        self._populate_table(mods)
        self._update_statistics(mods)
        self._set_idle(f"Found {len(mods)} mod(s)", "#4ec952")
        if self.status_manager:
            self.status_manager.push_status(f"Scan complete — {len(mods)} mod(s)", "success")

    @Slot(str)
    def _on_worker_error(self, msg: str):
        self._notify(f"✗ Error: {msg}", "error")
        self._set_idle("Error", "#d13438")
        if self.status_manager:
            self.status_manager.push_status("Operation failed", "error")

    @Slot(object, bool)
    def _on_check_complete(self, outdated: dict, was_refreshed: bool):
        self._mods.update(outdated)
        self._populate_table(self._mods)
        self._update_statistics(self._mods)
        n = len(outdated)
        label = f"{n} update(s) available" if n else "All up to date"
        self._set_idle(label, "#ffad00" if n else "#4ec952")
        if self.status_manager:
            self.status_manager.push_status(label, "warning" if n else "success")

    @Slot(list, list)
    def _on_update_complete(self, successful: list, failed: list):
        self._populate_table(self._mods)
        self._update_statistics(self._mods)
        if failed:
            self._notify(f"✗ Failed to update: {', '.join(failed)}", "error")
            self._set_idle("Update errors", "#d13438")
        else:
            self._notify(f"✓ Updated {len(successful)} mod(s)", "success")
            self._set_idle(f"Updated {len(successful)} mod(s)", "#4ec952")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_scan(self):
        if not self._ensure_logic():
            return
        self._set_busy("Scanning…")
        worker = ScanWorker(self._logic, parent=self)
        self._active_worker = worker
        worker.mods_loaded.connect(self._on_mods_loaded)
        worker.log_message.connect(self._append_op_log)
        worker.error.connect(self._on_worker_error)
        worker.start()

    def _on_check_updates(self):
        if not self._ensure_logic():
            return
        self._set_busy("Checking updates…")
        worker = UpdateCheckWorker(self._logic, force_refresh=True, parent=self)
        self._active_worker = worker
        worker.check_complete.connect(self._on_check_complete)
        worker.log_message.connect(self._append_op_log)
        worker.error.connect(self._on_worker_error)
        worker.start()

    def _on_update_selected(self):
        if not self._selected_mods or not self._ensure_logic():
            return
        self._set_busy(f"Updating {len(self._selected_mods)} mod(s)…")
        worker = UpdateSelectedWorker(
            self._logic, list(self._selected_mods), parent=self
        )
        self._active_worker = worker
        worker.update_complete.connect(self._on_update_complete)
        worker.log_message.connect(self._append_op_log)
        worker.error.connect(self._on_worker_error)
        worker.start()

    def _on_update_all(self):
        if not self._mods or not self._ensure_logic():
            return
        all_names = list(self._mods.keys())
        self._set_busy(f"Updating all {len(all_names)} mod(s)…")
        worker = UpdateSelectedWorker(self._logic, all_names, parent=self)
        self._active_worker = worker
        worker.update_complete.connect(self._on_update_complete)
        worker.log_message.connect(self._append_op_log)
        worker.error.connect(self._on_worker_error)
        worker.start()

    def _on_delete_clicked(self):
        if not self._selected_mods:
            return
        names = ", ".join(sorted(self._selected_mods))
        count = len(self._selected_mods)
        self._notify(
            f"Delete {count} mod(s)? ({names})",
            notif_type="warning",
            duration_ms=0,   # persistent
            actions=[("Delete", self._confirm_delete), ("Cancel", None)],
        )

    def _confirm_delete(self):
        if not self._ensure_logic():
            return
        folder = self.folder_edit.text().strip()
        try:
            successful, failed = self._logic.delete_mods(
                list(self._selected_mods), folder
            )
            for name in successful:
                self._mods.pop(name, None)
            self._selected_mods.difference_update(successful)
            self._populate_table(self._mods)
            self._update_statistics(self._mods)
            if failed:
                self._notify(f"✗ Could not delete: {', '.join(failed)}", "error")
            else:
                self._notify(f"✓ Deleted {len(successful)} mod(s)", "success")
        except Exception as exc:
            self._notify(f"✗ Delete error: {exc}", "error")
        self._update_button_states()

    def _on_backup(self):
        if not self._selected_mods or not self._ensure_logic():
            return
        folder = self.folder_edit.text().strip()
        try:
            successful, failed = self._logic.backup_mods(
                list(self._selected_mods), folder
            )
            if failed:
                self._notify(f"✗ Could not backup: {', '.join(failed)}", "error")
            else:
                self._notify(f"✓ Backed up {len(successful)} mod(s)", "success")
        except Exception as exc:
            self._notify(f"✗ Backup error: {exc}", "error")

    def _on_clean_backups_clicked(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            self._notify("Please select a mods folder first.", "warning")
            return
        backup_path = Path(folder) / "backup"
        if not backup_path.exists():
            self._notify("No backup folder found.", "info")
            return
        size_bytes = sum(
            f.stat().st_size for f in backup_path.rglob("*") if f.is_file()
        )
        size_str = format_file_size(size_bytes)
        self._notify(
            f"Delete backup folder? ({size_str}) This cannot be undone.",
            notif_type="warning",
            duration_ms=0,   # persistent
            actions=[("Delete", self._confirm_clean_backups), ("Cancel", None)],
        )

    def _confirm_clean_backups(self):
        if not self._ensure_logic():
            return
        folder = self.folder_edit.text().strip()
        try:
            self._logic.clean_backups(folder)
            self._notify("✓ Backup folder removed.", "success")
        except Exception as exc:
            self._notify(f"✗ Clean backups error: {exc}", "error")

    def _on_view_details(self):
        if len(self._selected_mods) != 1:
            return
        mod_name = next(iter(self._selected_mods))
        mod = self._mods.get(mod_name)
        if not mod:
            return
        title = mod.title or mod_name
        info_lines = [
            f"Name: {mod_name}",
            f"Title: {title}",
            f"Author: {mod.author or 'Unknown'}",
            f"Installed: {mod.version or '?'}",
            f"Latest: {mod.latest_version or '?'}",
            f"Status: {mod.status.name}",
        ]
        self._notify("\n".join(info_lines), "info", duration_ms=8000)
