"""Checker tab UI — Qt implementation."""
from __future__ import annotations

import html as html_lib
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
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
from ..core.mod_list import ModListStore
from ..core.profiles import CURATED_PRESETS, ProfileStore, build_diff
from ..core.queue_models import (
    OperationKind,
    OperationSource,
    OperationState,
    QueueOperation,
)
from ..core.update_guidance import UpdateClassification, GuidanceResult
from ..utils import config, format_file_size, is_online
from .widgets import NotificationManager
from .checker_logic import CheckerLogic
from .checker_presenter import CheckerPresenter
from .filter_sort_bar import FilterSortBar
from .queue_strip import QueueStrip
from .update_queue_job import UpdateQueueJob


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
# Worker: ClassifyWorker
# ---------------------------------------------------------------------------

class ClassifyWorker(QThread):
    """Runs CheckerLogic.classify_updates() in a background thread."""

    guidance_ready = Signal(object)   # dict[str, GuidanceResult]
    error = Signal(str)

    def __init__(self, checker_logic: CheckerLogic, mods: dict, parent=None):
        super().__init__(parent)
        self._logic = checker_logic
        self._mods = dict(mods)   # snapshot to avoid races

    def run(self) -> None:
        try:
            results = self._logic.classify_updates(self._mods)
            self.guidance_ready.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# SmartUpdateStrip
# ---------------------------------------------------------------------------

class SmartUpdateStrip(QWidget):
    """Full-width strip showing guidance counts and Queue Safe Updates CTA."""

    queue_safe_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("smartUpdateStrip")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        self._summary_lbl = QLabel("No update guidance yet")
        self._summary_lbl.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._summary_lbl, stretch=1)

        self._safe_lbl = QLabel("0 Safe")
        self._safe_lbl.setStyleSheet("color: #4ec952; font-weight: bold;")
        self._review_lbl = QLabel("0 Review")
        self._review_lbl.setStyleSheet("color: #ffad00; font-weight: bold;")
        self._risky_lbl = QLabel("0 Risky")
        self._risky_lbl.setStyleSheet("color: #d13438; font-weight: bold;")
        for chip in (self._safe_lbl, self._review_lbl, self._risky_lbl):
            layout.addWidget(chip)

        self._why_lbl = QLabel("Why not all?")
        self._why_lbl.setObjectName("searchResultMeta")
        self._why_lbl.setToolTip(
            "Safe batch is conservative by design.\n"
            "Review and Risky items stay manual so you can inspect before queueing."
        )
        self._why_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        layout.addWidget(self._why_lbl)

        self._queue_safe_btn = QPushButton("Queue Safe Updates")
        self._queue_safe_btn.setObjectName("accentButton")
        self._queue_safe_btn.setEnabled(False)
        self._queue_safe_btn.clicked.connect(self.queue_safe_requested)
        layout.addWidget(self._queue_safe_btn)

    def update_guidance(self, scope_mods: list, guidance: dict) -> None:
        """Refresh strip counts for the given scope."""
        safe = sum(
            1 for n in scope_mods
            if guidance.get(n) and guidance[n].classification == UpdateClassification.SAFE
        )
        review = sum(
            1 for n in scope_mods
            if guidance.get(n) and guidance[n].classification == UpdateClassification.REVIEW
        )
        risky = sum(
            1 for n in scope_mods
            if guidance.get(n) and guidance[n].classification == UpdateClassification.RISKY
        )
        total = safe + review + risky

        self._safe_lbl.setText(f"{safe} Safe")
        self._review_lbl.setText(f"{review} Review")
        self._risky_lbl.setText(f"{risky} Risky")

        if total == 0:
            self._summary_lbl.setText(
                "No update guidance yet \u2014 run Check for Updates to classify mods."
            )
        else:
            self._summary_lbl.setText(f"Guidance for {total} outdated mod(s):")

        self._queue_safe_btn.setEnabled(safe > 0)


# ---------------------------------------------------------------------------
# _UpdateConfirmDialog
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QDialog as _QDialog


class _UpdateConfirmDialog(QDialog):
    """Confirmation dialog shown when Review/Risky mods are in the selection."""

    def __init__(self, safe: int, review: int, risky: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Update Queue")
        self.setModal(True)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        msg = QLabel(
            f"Queue selected updates for confirmed mods?\n\n"
            f"  \u2713 Safe: {safe}    \u26a0 Review: {review}    \u2717 Risky: {risky}\n\n"
            "Review and Risky items need explicit confirmation before entering the queue."
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(msg)

        btns = QHBoxLayout()
        queue_btn = QPushButton("Queue Selected")
        queue_btn.setObjectName("accentButton")
        queue_btn.clicked.connect(self.accept)
        details_btn = QPushButton("View Details")
        details_btn.clicked.connect(lambda: self.done(2))
        cancel_btn = QPushButton("Return to Checker")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(queue_btn)
        btns.addWidget(details_btn)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)


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
    mods_loaded = Signal(object)      # emits Dict[str, Mod] after each successful scan

    def __init__(self, logger=None, status_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logger or logging.getLogger(__name__)
        self.status_manager = status_manager
        self.notification_manager: Optional[NotificationManager] = None

        self._queue_controller = None    # injected by MainWindow after construction
        self._active_jobs: dict = {}     # op_id → UpdateQueueJob / ProfileApplyJob
        self._queue_progress_handlers: dict = {}  # op_id → connected lambda, for cleanup
        self._queue_changed_handler = None  # stored lambda for queue_changed connection
        self._current_apply_op_id: Optional[str] = None  # undo invalidation tracking
        self._profile_store = ProfileStore()             # for snapshot undo

        self._first_show = True          # auto-scan guard
        self._mods: Dict[str, Mod] = {}
        self._selected_mods: set = set()
        self._current_filter = "all"
        self._current_sort = "name"
        self._search_query = ""
        self._active_worker = None       # prevents GC before signal delivery
        self._classify_worker = None     # ClassifyWorker reference

        self._guidance: dict = {}        # name → GuidanceResult
        self._guidance_filter = "any"    # "any" | "safe" | "review" | "risky"

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

    def set_queue_controller(self, controller) -> None:
        """Inject the shared QueueController (called by MainWindow)."""
        self._queue_controller = controller
        # Wire undo restore: QueueDrawer duck-types _undo_callback on the controller
        controller._undo_callback = self._on_undo_restore_callback
        if hasattr(self, "_queue_strip"):
            if self._queue_changed_handler:
                try:
                    controller.queue_changed.disconnect(self._queue_changed_handler)
                except RuntimeError:
                    pass
            self._queue_changed_handler = lambda ops: self._queue_strip.update_from_operations(ops)
            controller.queue_changed.connect(self._queue_changed_handler)

    def _notify(self, message, notif_type="info", duration_ms=4000, actions=None):
        if self.notification_manager is not None:
            self.notification_manager.show(
                message,
                notification_type=notif_type,
                duration_ms=duration_ms,
                actions=actions,
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        page_title = QLabel("Checker & Updates")
        page_title.setObjectName("pageTitle")
        header_layout.addWidget(page_title)
        header_layout.addStretch()

        self._header_profiles_btn = QPushButton("Profiles")
        self._header_profiles_btn.clicked.connect(self._on_open_profiles)
        header_layout.addWidget(self._header_profiles_btn)

        self._header_scan_btn = QPushButton("\u21bb")
        self._header_scan_btn.setObjectName("refreshButton")
        self._header_scan_btn.setFixedSize(28, 28)
        self._header_scan_btn.setToolTip("Rescan mods folder (F5)")
        self._header_scan_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self._header_scan_btn)

        self._header_check_btn = QPushButton("Check for Updates")
        self._header_check_btn.setObjectName("accentButton")
        self._header_check_btn.clicked.connect(self._on_check_updates)
        header_layout.addWidget(self._header_check_btn)
        root.addWidget(header)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(8, 8, 8, 8)
        workspace_layout.setSpacing(8)
        root.addWidget(workspace, stretch=1)

        # Main splitter: left | center | right
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self._splitter

        # ----- LEFT SIDEBAR (220 px fixed) -----
        left_widget = QWidget()
        left_widget.setMinimumWidth(180)
        left_widget.setMaximumWidth(260)
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
        self.status_label.setObjectName("checkerStatusLabel")
        self.status_label.setProperty("statusType", "ready")
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
        self.mod_table.setColumnCount(8)
        self.mod_table.setHorizontalHeaderLabels(
            ["✔", "On", "Name", "Status", "Guidance", "Version", "Author", "Downloads"]
        )
        self.mod_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mod_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.mod_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.mod_table.setColumnWidth(0, 30)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.mod_table.setColumnWidth(1, 35)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.setAlternatingRowColors(True)

        # ----- RIGHT SIDEBAR (280 px fixed) -----
        right_widget = QWidget()
        right_widget.setMinimumWidth(220)
        right_widget.setMaximumWidth(360)
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
            stats_vbox.addWidget(lbl)
        right_layout.addWidget(stats_group)

        # Selected Update Guidance panel
        self._guidance_group = QGroupBox("Selected Update Guidance")
        guidance_vbox = QVBoxLayout(self._guidance_group)
        self._guidance_empty_lbl = QLabel(
            "No update guidance yet\n\nRun Check for Updates to classify installed mods "
            "and surface safe, review, and risky recommendations."
        )
        self._guidance_empty_lbl.setWordWrap(True)
        self._guidance_empty_lbl.setObjectName("searchResultMeta")
        guidance_vbox.addWidget(self._guidance_empty_lbl)
        self._guidance_chip_lbl = QLabel()
        self._guidance_chip_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._guidance_chip_lbl.setVisible(False)
        guidance_vbox.addWidget(self._guidance_chip_lbl)
        self._guidance_rationale_lbl = QLabel()
        self._guidance_rationale_lbl.setWordWrap(True)
        self._guidance_rationale_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._guidance_rationale_lbl.setVisible(False)
        guidance_vbox.addWidget(self._guidance_rationale_lbl)
        self._guidance_delta_lbl = QLabel()
        self._guidance_delta_lbl.setWordWrap(True)
        self._guidance_delta_lbl.setObjectName("searchResultMeta")
        self._guidance_delta_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._guidance_delta_lbl.setVisible(False)
        guidance_vbox.addWidget(self._guidance_delta_lbl)
        self._guidance_details_btn = QPushButton("View Details")
        self._guidance_details_btn.setVisible(False)
        self._guidance_details_btn.clicked.connect(self._on_view_details_from_guidance)
        guidance_vbox.addWidget(self._guidance_details_btn)
        right_layout.addWidget(self._guidance_group)

        right_layout.addStretch()

        # Add panes to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(self.mod_table)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)

        # Filter/sort toolbar — full width above the table, below the splitter
        self._filter_bar = FilterSortBar()
        self._filter_bar.add_priority_combo(
            ["Any priority", "Outdated", "Selected", "Errors"]
        )
        self._filter_bar.add_guidance_combo()
        self._filter_bar.filter_changed.connect(self._on_filter_bar_changed)
        self._filter_bar.guidance_changed.connect(self._on_guidance_filter_changed)
        workspace_layout.addWidget(self._filter_bar)

        # Inline queue strip — shown when checker updates are queued (between filter bar and table)
        self._queue_strip = QueueStrip(source_filter=OperationSource.CHECKER)
        self._queue_strip.open_queue_requested.connect(self._on_open_queue_requested)
        workspace_layout.addWidget(self._queue_strip)

        # Smart update strip — guidance summary above mod table
        self._smart_strip = SmartUpdateStrip()
        self._smart_strip.queue_safe_requested.connect(self._on_queue_safe_updates)
        workspace_layout.addWidget(self._smart_strip)

        workspace_layout.addWidget(splitter, stretch=1)
        self.op_log = QTextEdit()
        self.op_log.setReadOnly(True)
        self.op_log.setFixedHeight(120)
        self.op_log.setFont(QFont("Cascadia Code", 9))
        self.op_log.setPlaceholderText("Operation log…")
        workspace_layout.addWidget(self.op_log)

        # Initial button state
        self._update_button_states()

    def _set_status_type(self, status_type: str):
        self.status_label.setProperty("statusType", status_type)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _restore_config(self):
        saved = config.get("mods_folder", "")
        if saved:
            self.folder_edit.setText(str(saved))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rescan the mods folder (local only, no portal call)."""
        self._on_scan()

    # showEvent — auto-scan on first tab visit
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        # Defer splitter sizing until Qt has assigned real geometry
        QTimer.singleShot(0, self._apply_splitter_sizes)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(3000, self._auto_scan)

    def _apply_splitter_sizes(self) -> None:
        total = self._splitter.width()
        if total > 0:
            center = max(100, total - 220 - 280)
            self._splitter.setSizes([220, center, 280])

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

        # Apply guidance filter
        if self._guidance_filter != "any":
            filtered = [
                (n, m) for n, m in filtered
                if n in self._guidance
                and self._guidance[n].classification.value == self._guidance_filter
            ]

        self.mod_table.setRowCount(0)
        self.mod_table.setRowCount(len(filtered))

        for row, (mod_name, mod) in enumerate(filtered):
            # Col 0: bulk-select checkbox
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

            # Col 1: enabled toggle (D-14 — separate from bulk-select)
            enabled_chk = QCheckBox()
            enabled_chk.setChecked(getattr(mod, "enabled", True))
            enabled_chk.setToolTip("Enable / disable this mod (keeps ZIP on disk)")
            enabled_chk.stateChanged.connect(
                lambda state, name=mod_name: self._on_enabled_changed(name, state)
            )
            en_cell = QWidget()
            en_layout = QHBoxLayout(en_cell)
            en_layout.addWidget(enabled_chk)
            en_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            en_layout.setContentsMargins(0, 0, 0, 0)
            self.mod_table.setCellWidget(row, 1, en_cell)

            # Col 2: name
            name_item = QTableWidgetItem(mod_name)
            name_item.setData(Qt.ItemDataRole.UserRole, mod_name)
            self.mod_table.setItem(row, 2, name_item)

            # Col 3: status
            status_text, color = _STATUS_COLORS.get(
                mod.status, ("❓ Unknown", "#b0b0b0")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            self.mod_table.setItem(row, 3, status_item)

            # Col 4: guidance chip (outdated mods only)
            guidance_text = ""
            guidance_color = ""
            if mod.status == ModStatus.OUTDATED and mod_name in self._guidance:
                g = self._guidance[mod_name]
                if g.classification == UpdateClassification.SAFE:
                    guidance_text, guidance_color = "Safe", "#4ec952"
                elif g.classification == UpdateClassification.REVIEW:
                    guidance_text, guidance_color = "Review", "#ffad00"
                elif g.classification == UpdateClassification.RISKY:
                    guidance_text, guidance_color = "Risky", "#d13438"
            guidance_item = QTableWidgetItem(guidance_text)
            if guidance_color:
                guidance_item.setForeground(QColor(guidance_color))
            self.mod_table.setItem(row, 4, guidance_item)

            # Col 5: version
            installed = mod.version or "?"
            latest = mod.latest_version or "?"
            version_text = f"{installed} → {latest}" if mod.status == ModStatus.OUTDATED else installed
            self.mod_table.setItem(row, 5, QTableWidgetItem(version_text))

            # Col 6: author
            self.mod_table.setItem(row, 6, QTableWidgetItem(mod.author or ""))

            # Col 7: downloads
            self.mod_table.setItem(row, 7, QTableWidgetItem(str(mod.downloads or "")))

            # Dim text columns for disabled mods (D-14 visual treatment)
            if not getattr(mod, "enabled", True):
                dim = QColor("#888888")
                for col_idx in (2, 3, 4, 5, 6, 7):
                    item = self.mod_table.item(row, col_idx)
                    if item:
                        item.setForeground(dim)

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

    def _on_filter_bar_changed(self, query: str, status: str, sort_by: str, priority: str) -> None:
        self._search_query = query
        self._current_filter = status
        self._current_sort = sort_by
        if self._mods:
            self._populate_table(self._mods)

    def _on_checkbox_changed(self, mod_name: str, state: int):
        if state == Qt.CheckState.Checked.value:
            self._selected_mods.add(mod_name)
        else:
            self._selected_mods.discard(mod_name)
        self._update_button_states()
        self._update_smart_strip()
        self._update_guidance_panel()

    def _on_enabled_changed(self, mod_name: str, state: int) -> None:
        """Rename mod ZIP to .zip.bak (disable) or back to .zip (enable)."""
        if not self._logic:
            return
        enabled = state == Qt.CheckState.Checked.value
        try:
            if enabled:
                self._logic.enable_mod(mod_name)
            else:
                self._logic.disable_mod(mod_name)
        except Exception as exc:
            self._notify(
                f"\u2717 Could not {'enable' if enabled else 'disable'} {mod_name}: {exc}",
                "error",
            )
            return
        # Update row dim treatment
        dim = QColor("#888888")
        normal = QColor()  # default foreground
        for row in range(self.mod_table.rowCount()):
            name_item = self.mod_table.item(row, 2)
            if name_item and name_item.data(Qt.ItemDataRole.UserRole) == mod_name:
                for col_idx in (2, 3, 4, 5, 6, 7):
                    item = self.mod_table.item(row, col_idx)
                    if item:
                        item.setForeground(dim if not enabled else normal)
                break

    def _on_open_queue_requested(self) -> None:
        """Forward queue-strip 'Open Queue' clicks to the main window."""
        main_win = self.window()
        if hasattr(main_win, "open_queue_drawer"):
            main_win.open_queue_drawer()

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
        self._set_status_type("busy")
        self.scan_btn.setEnabled(False)

    def _set_idle(self, label: str = "Ready", color: str = "#4ec952"):
        self.status_label.setText(label)
        if color == "#d13438":
            self._set_status_type("error")
        elif color == "#ffad00":
            self._set_status_type("warning")
        elif color == "#4ec952":
            self._set_status_type("ready")
        else:
            self._set_status_type("neutral")
        self.scan_btn.setEnabled(True)
        self._active_worker = None
        self._update_button_states()

    @Slot(object)
    def _on_mods_loaded(self, mods: dict):
        self._mods = mods
        self.mods_loaded.emit(mods)
        self._populate_table(mods)
        self._update_statistics(mods)
        n_active = sum(1 for m in mods.values() if m.enabled)
        n_disabled = len(mods) - n_active
        label = f"Found {len(mods)} mod(s)"
        if n_disabled:
            label += f" ({n_disabled} disabled)"
        self._set_idle(label, "#4ec952")
        if self.status_manager:
            self.status_manager.push_status(f"Scan complete — {label}", "success")
        self._start_classify(mods)

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
        self._start_classify(self._mods)

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

    def _on_open_profiles(self) -> None:
        """Open the profile library dialog from the Checker header."""
        from .profile_library_dialog import ProfileLibraryDialog

        folder = self.folder_edit.text().strip()
        if not folder or not self._mods:
            self._notify("Please scan mods first before using profiles.", "warning")
            return

        dlg = ProfileLibraryDialog(
            folder,
            installed_mods=self._mods,
            queue_controller=self._queue_controller,
            parent=self,
        )
        dlg.profile_selected.connect(self._on_profile_selected)
        dlg.exec()

    def _on_profile_selected(self, profile_identifier: str) -> None:
        """Resolve profile, compute diff, confirm via dialog, and enqueue apply job."""
        from .profile_apply_dialog import ProfileApplyDialog
        from .profile_apply_job import ProfileApplyJob

        folder = self.folder_edit.text().strip()
        # Guard: pre-check in _on_open_profiles prevents reaching here without mods,
        # but keep as a safety net for direct callers.
        if not folder or not self._mods:
            self._notify("Please scan mods first.", "warning")
            return

        # --- Resolve profile object ---
        profile = None
        # Try saved profiles first
        for p in self._profile_store.load_all():
            if p.name == profile_identifier:
                profile = p
                break
        # Try curated presets
        if profile is None:
            from ..core.profiles import PresetSeed, Profile
            for seed in CURATED_PRESETS:
                if seed.family.value == profile_identifier:
                    import uuid as _uuid
                    profile = Profile(
                        id=str(_uuid.uuid4()),
                        name=seed.family.value,
                        desired_mods=list(seed.mod_names),
                    )
                    break
        if profile is None:
            self._notify(f"Profile '{profile_identifier}' not found.", "error")
            return

        # --- Build diff ---
        # Use mod-list.json as the authoritative source for current enabled states.
        from pathlib import Path as _Path
        from ..core.mod_list import ModListStore as _ModListStore
        installed_names = list(self._mods.keys())
        current_enabled = _ModListStore(_Path(folder)).load()
        # Fall back to Mod.enabled for any mod not yet written to mod-list.json
        for mod_name, mod in self._mods.items():
            if mod_name not in current_enabled:
                current_enabled[mod_name] = getattr(mod, "enabled", True)
        diff = build_diff(profile, installed_names, current_enabled, self._mods)

        if diff.is_empty:
            self._notify("No changes needed — already at this profile state.", "info")
            return

        # --- Confirm via dialog ---
        from PySide6.QtWidgets import QDialog
        dlg = ProfileApplyDialog(diff, profile, self._profile_store, parent=self)
        dlg.download_requested.connect(self._on_profile_download_requested)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Use the user-adjusted diff (may have unchecked items removed)
        effective_diff = dlg.accepted_diff()

        if self._queue_controller is None:
            self._notify("Queue controller not available.", "error")
            return

        # --- Invalidate previous apply undo ---
        if self._current_apply_op_id:
            self._queue_controller.invalidate_undo(self._current_apply_op_id)

        # --- Enqueue apply job ---
        op = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.PROFILE_APPLY,
            label=f"Apply {profile.name}",
        )
        job = ProfileApplyJob(op, effective_diff, profile, self._profile_store, folder, self._mods, parent=self)
        self._active_jobs[op.id] = job
        self._current_apply_op_id = op.id

        self._queue_controller.enqueue(op)
        self._queue_controller.start_next()
        job.start(self._queue_controller)
        _handler = lambda ops, _id=op.id: self._on_apply_queue_progress(ops, _id)
        self._queue_progress_handlers[op.id] = _handler
        self._queue_controller.queue_changed.connect(_handler)
        self._notify(f"Queued: Apply {profile.name}", "info")

    def _on_apply_queue_progress(self, operations, op_id: str) -> None:
        """React to queue state changes for the active profile apply operation."""
        for op in operations:
            if op.id != op_id:
                continue
            if op.state == OperationState.COMPLETED:
                self._notify(
                    "✓ Profile applied successfully",
                    "success",
                    duration_ms=10000,
                    actions=[("Undo Restore", lambda _id=op_id: self._trigger_undo(_id))],
                )
                self._active_jobs.pop(op_id, None)
                self._disconnect_queue_handler(op_id)
                # Refresh table to reflect new enabled states
                if self._logic:
                    self._on_scan()
            elif op.state == OperationState.FAILED:
                msg = op.failure.short_description if op.failure else "Unknown error"
                self._notify(f"✗ Profile apply failed: {msg}", "error")
                self._active_jobs.pop(op_id, None)
                self._disconnect_queue_handler(op_id)
            break

    def _trigger_undo(self, operation_id: str) -> None:
        """Called from the 'Undo Restore' toast action."""
        if self._queue_controller:
            self._on_undo_restore_callback(operation_id)

    def _on_profile_download_requested(self, mod_names: list) -> None:
        """Enqueue download jobs for mods requested from the profile apply/edit dialogs."""
        if self._queue_controller is None:
            self._notify("Queue controller not available for download.", "warning")
            return
        from .download_queue_job import DownloadQueueJob
        folder = self.folder_edit.text().strip()
        for mod_name in mod_names:
            dl_op = QueueOperation(
                source=OperationSource.CHECKER,
                kind=OperationKind.DOWNLOAD,
                label=f"Download {mod_name} (profile)",
                continue_on_failure=True,
            )
            dl_job = DownloadQueueJob(
                dl_op,
                f"https://mods.factorio.com/mod/{mod_name}",
                folder,
                parent=self,
            )
            self._queue_controller.enqueue(dl_op)
            self._queue_controller.start_next()
            dl_job.start(self._queue_controller)
        if mod_names:
            self._notify(
                f"Queued {len(mod_names)} download(s) from profile.",
                "info",
            )

    def _disconnect_queue_handler(self, op_id: str) -> None:
        """Disconnect and remove the per-operation queue_changed handler."""
        handler = self._queue_progress_handlers.pop(op_id, None)
        if handler and self._queue_controller:
            try:
                self._queue_controller.queue_changed.disconnect(handler)
            except RuntimeError:
                pass

    def _on_undo_restore_callback(self, operation_id: str) -> None:
        """Restore mod-list.json from the apply snapshot (called by QueueDrawer)."""
        if not self._queue_controller:
            return
        op = self._queue_controller.get_operation(operation_id)
        if op is None or not op.snapshot_id:
            self._notify("Undo snapshot not available.", "warning")
            return
        snapshot = self._profile_store.load_snapshot(op.snapshot_id)
        if snapshot is None or not snapshot.valid:
            self._notify("Undo snapshot has already been used or is unavailable.", "warning")
            return

        # Restore mod-list.json from snapshot
        ml = ModListStore(Path(self.folder_edit.text().strip()))
        for mod_name, was_enabled in snapshot.enabled_before.items():
            if was_enabled:
                ml.enable(mod_name)
            else:
                ml.disable(mod_name)

        # Invalidate snapshot and undo token
        self._profile_store.invalidate_snapshot(op.snapshot_id)
        self._queue_controller.invalidate_undo(operation_id)
        self._current_apply_op_id = None

        self._notify("✓ Restored to previous state.", "success")
        # Refresh table
        if self._logic:
            self._on_scan()

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

        # Check if any selected mods are Review or Risky
        non_safe = [
            n for n in self._selected_mods
            if n in self._guidance
            and self._guidance[n].classification != UpdateClassification.SAFE
        ]
        if non_safe and self._guidance:
            safe_count   = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.SAFE)
            review_count = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.REVIEW)
            risky_count  = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.RISKY)
            dlg = _UpdateConfirmDialog(safe_count, review_count, risky_count, parent=self)
            result = dlg.exec()
            if result == QDialog.DialogCode.Rejected:
                return
            elif result == 2:  # "View Details"
                self._on_view_details()
                return
            # result == Accepted → proceed with queue

        if self._queue_controller is not None:
            mod_names = list(self._selected_mods)
            label = f"Update {len(mod_names)} mod(s)"
            op = QueueOperation(
                source=OperationSource.CHECKER,
                kind=OperationKind.UPDATE,
                label=label,
            )
            job = UpdateQueueJob(op, mod_names, self._logic, parent=self)
            self._active_jobs[op.id] = job
            self._queue_controller.enqueue(op)
            self._queue_controller.start_next()
            job.start(self._queue_controller)
            _handler = lambda ops, _id=op.id: self._on_update_queue_progress(ops, _id)
            self._queue_progress_handlers[op.id] = _handler
            self._queue_controller.queue_changed.connect(_handler)
            self._notify(f"Queued: {label}", "info")
            return

        # Legacy fallback
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

        if self._queue_controller is not None:
            mod_names = list(self._mods.keys())
            label = f"Update all {len(mod_names)} mod(s)"
            op = QueueOperation(
                source=OperationSource.CHECKER,
                kind=OperationKind.UPDATE,
                label=label,
            )
            job = UpdateQueueJob(op, mod_names, self._logic, parent=self)
            self._active_jobs[op.id] = job
            self._queue_controller.enqueue(op)
            self._queue_controller.start_next()
            job.start(self._queue_controller)
            _handler = lambda ops, _id=op.id: self._on_update_queue_progress(ops, _id)
            self._queue_progress_handlers[op.id] = _handler
            self._queue_controller.queue_changed.connect(_handler)
            self._notify(f"Queued: {label}", "info")
            return

        all_names = list(self._mods.keys())
        self._set_busy(f"Updating all {len(all_names)} mod(s)…")
        worker = UpdateSelectedWorker(self._logic, all_names, parent=self)
        self._active_worker = worker
        worker.update_complete.connect(self._on_update_complete)
        worker.log_message.connect(self._append_op_log)
        worker.error.connect(self._on_worker_error)
        worker.start()

    def _on_update_queue_progress(self, operations: list, op_id: str) -> None:
        """Mirror queue-controller update state into status label and toasts."""
        for op in operations:
            if op.id != op_id:
                continue
            if op.state == OperationState.COMPLETED:
                job = self._active_jobs.get(op_id)
                successful = job.mod_names if job is not None else []
                self._on_update_complete(successful, [])  # trigger table refresh
                self._notify("✓ Update complete", "success")
                self._active_jobs.pop(op_id, None)
                self._disconnect_queue_handler(op_id)
            elif op.state == OperationState.FAILED:
                short = op.failure.short_description if op.failure else "Update failed"
                self._notify(f"✗ {short}", "error")
                self._active_jobs.pop(op_id, None)
                self._disconnect_queue_handler(op_id)
            break

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
        from .mod_details_dialog import ModDetailsDialog
        dlg = ModDetailsDialog(data=mod, source="installed", parent=self,
                               installed_mods=self._mods)
        dlg.exec()

    def _on_view_details_from_guidance(self) -> None:
        """View Details from the guidance panel — deep-links to Dependencies tab."""
        if len(self._selected_mods) != 1:
            return
        mod_name = next(iter(self._selected_mods))
        mod = self._mods.get(mod_name)
        if not mod:
            return
        from .mod_details_dialog import ModDetailsDialog
        dlg = ModDetailsDialog(data=mod, source="installed", parent=self,
                               installed_mods=self._mods, initial_tab="dependencies")
        dlg.exec()

    def _start_classify(self, mods: dict) -> None:
        """Kick off background guidance classification for all loaded mods."""
        if not self._logic or not mods:
            return
        # Cancel any in-flight classifier so its stale results won't overwrite ours
        if self._classify_worker is not None and self._classify_worker.isRunning():
            self._classify_worker.guidance_ready.disconnect()
            self._classify_worker.requestInterruption()
            self._classify_worker.quit()
            self._classify_worker = None
        worker = ClassifyWorker(self._logic, mods, parent=self)
        worker.guidance_ready.connect(self._on_guidance_ready)
        worker.error.connect(lambda msg: self.logger.warning("Classify error: %s", msg))
        worker.start()
        self._classify_worker = worker

    @Slot(object)
    def _on_guidance_ready(self, results: dict) -> None:
        """Receive classified guidance dict from ClassifyWorker."""
        self._guidance = results
        self._update_smart_strip()
        self._update_guidance_panel()
        if self._mods:
            self._populate_table(self._mods)

    def _update_smart_strip(self) -> None:
        """Recompute SmartUpdateStrip scope and refresh counts."""
        if not hasattr(self, "_smart_strip"):
            return
        if self._selected_mods:
            scope = [
                n for n in self._selected_mods
                if self._mods.get(n) and self._mods[n].status == ModStatus.OUTDATED
            ]
        else:
            filtered = self._presenter.filter_mods(
                self._mods, self._search_query, self._current_filter,
                self._selected_mods, self._current_sort,
            )
            scope = [n for n, m in filtered if m.status == ModStatus.OUTDATED]
        self._smart_strip.update_guidance(scope, self._guidance)

    def _update_guidance_panel(self) -> None:
        """Refresh the Selected Update Guidance panel for current selection."""
        if not hasattr(self, "_guidance_group"):
            return
        n_selected = len(self._selected_mods)

        if n_selected == 0:
            self._guidance_empty_lbl.setText(
                "No update guidance yet\n\nRun Check for Updates to classify installed mods "
                "and surface safe, review, and risky recommendations."
            )
            self._guidance_empty_lbl.setVisible(True)
            for w in (self._guidance_chip_lbl, self._guidance_rationale_lbl,
                      self._guidance_delta_lbl, self._guidance_details_btn):
                w.setVisible(False)

        elif n_selected == 1:
            mod_name = next(iter(self._selected_mods))
            result = self._guidance.get(mod_name)
            if result is None:
                self._guidance_empty_lbl.setText(
                    "No guidance available \u2014 run Check for Updates first."
                )
                self._guidance_empty_lbl.setVisible(True)
                for w in (self._guidance_chip_lbl, self._guidance_rationale_lbl,
                          self._guidance_delta_lbl, self._guidance_details_btn):
                    w.setVisible(False)
                return

            self._guidance_empty_lbl.setVisible(False)
            chip_text, chip_color = CheckerPresenter.guidance_chip_info(
                result.classification
            )
            self._guidance_chip_lbl.setText(chip_text)
            self._guidance_chip_lbl.setStyleSheet(
                f"color: {chip_color}; font-weight: bold;"
            )
            self._guidance_chip_lbl.setVisible(True)

            self._guidance_rationale_lbl.setText(
                "\n".join(f"\u2022 {r}" for r in result.rationale)
            )
            self._guidance_rationale_lbl.setVisible(True)

            self._guidance_delta_lbl.setText(result.dep_delta_summary)
            self._guidance_delta_lbl.setVisible(True)

            self._guidance_details_btn.setVisible(True)

        else:
            safe_n   = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.SAFE)
            review_n = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.REVIEW)
            risky_n  = sum(1 for n in self._selected_mods if self._guidance.get(n) and self._guidance[n].classification == UpdateClassification.RISKY)
            self._guidance_empty_lbl.setText(
                f"{n_selected} mods selected\n\u2713 Safe: {safe_n}  \u26a0 Review: {review_n}  \u2717 Risky: {risky_n}\n\n"
                "Only Safe items enter the one-click batch. Review and Risky items stay manual."
            )
            self._guidance_empty_lbl.setVisible(True)
            for w in (self._guidance_chip_lbl, self._guidance_rationale_lbl,
                      self._guidance_delta_lbl, self._guidance_details_btn):
                w.setVisible(False)

    def _on_queue_safe_updates(self) -> None:
        """Queue only mods classified Safe in the current scope."""
        if not self._ensure_logic() or self._queue_controller is None:
            return
        if self._selected_mods:
            scope = [
                n for n in self._selected_mods
                if self._mods.get(n) and self._mods[n].status == ModStatus.OUTDATED
            ]
        else:
            filtered = self._presenter.filter_mods(
                self._mods, self._search_query, self._current_filter,
                self._selected_mods, self._current_sort,
            )
            scope = [n for n, m in filtered if m.status == ModStatus.OUTDATED]
        safe_names = [
            n for n in scope
            if n in self._guidance
            and self._guidance[n].classification == UpdateClassification.SAFE
        ]
        if not safe_names:
            self._notify("No Safe updates in current scope.", "info")
            return
        label = f"Queue Safe Updates ({len(safe_names)} mod(s))"
        op = QueueOperation(
            source=OperationSource.CHECKER,
            kind=OperationKind.UPDATE,
            label=label,
        )
        job = UpdateQueueJob(op, safe_names, self._logic, parent=self)
        self._active_jobs[op.id] = job
        self._queue_controller.enqueue(op)
        self._queue_controller.start_next()
        job.start(self._queue_controller)
        _handler = lambda ops, _id=op.id: self._on_update_queue_progress(ops, _id)
        self._queue_progress_handlers[op.id] = _handler
        self._queue_controller.queue_changed.connect(_handler)
        self._notify(
            f"Queued: {label}\nOnly Safe updates are queued here. "
            "Review and Risky items stay manual.",
            "info",
        )

    def _on_guidance_filter_changed(self, guidance: str) -> None:
        self._guidance_filter = guidance
        if self._mods:
            self._populate_table(self._mods)
        self._update_smart_strip()
