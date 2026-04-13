"""Downloader tab UI — Qt implementation."""
from __future__ import annotations

import html as html_lib
import logging
import re
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import ModDownloader, ModListStore
from ..core.portal import FactorioPortalAPI, PortalAPIError
from ..core.queue_models import (
    OperationKind,
    OperationSource,
    OperationState,
    QueueOperation,
)
from ..utils import config, is_online
from .download_coordinator_job import DownloadCoordinatorJob
from .queue_strip import QueueStrip
from .widgets import NotificationManager
from .filter_sort_bar import CategoryChipsBar, VersionFilterBar


# ---------------------------------------------------------------------------
# Worker: DownloadWorker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """QThread that runs ModDownloader.download_mod() and emits typed signals."""

    progress = Signal(int, int)     # (completed_count, total_count)
    mod_status = Signal(str, str)   # (mod_name, status_text)
    log_message = Signal(str, str)  # (message, level_name)
    finished = Signal(bool, list)   # (all_succeeded, failed_mod_names)

    def __init__(self, mod_url, mods_folder, include_optional=False, extra_mods=None, parent=None):
        super().__init__(parent)
        self._mod_url = mod_url
        self._mods_folder = mods_folder
        self._include_optional = include_optional
        self._extra_mods = extra_mods or []

    def run(self):
        try:
            downloader = ModDownloader(self._mods_folder)

            def _on_progress(completed, total):
                self.progress.emit(completed, total)
                if total > 0:
                    pct = int(completed / total * 100)
                    self.log_message.emit(
                        f"Downloading: {completed}/{total} mods ({pct}%)", "INFO"
                    )

            def _on_mod_status(mod_name, status, pct=None):
                self.mod_status.emit(mod_name, status)

            downloader.set_overall_progress_callback(_on_progress)
            downloader.set_mod_progress_callback(_on_mod_status)
            downloader.set_progress_callback(lambda msg: self.log_message.emit(msg, "INFO"))

            # Extract mod name from URL or treat input as a bare mod name
            import re as _re
            m = _re.search(r'/mod/([^/?&\s]+)', self._mod_url)
            mod_name = m.group(1) if m else self._mod_url.strip()

            mod_list = [mod_name] + [m for m in self._extra_mods if m != mod_name]
            _downloaded, failed = downloader.download_mods(
                mod_list, include_optional=self._include_optional
            )
            self.finished.emit(len(failed) == 0, failed)
        except PortalAPIError as exc:
            self.log_message.emit(str(exc), "ERROR")
            self.finished.emit(False, [])
        except Exception as exc:
            self.log_message.emit(f"Unexpected error: {exc}", "ERROR")
            self.finished.emit(False, [])


# ---------------------------------------------------------------------------
# Worker: ResolveWorker
# ---------------------------------------------------------------------------

class ResolveWorker(QThread):
    """QThread that resolves a mod URL to a mod info dict (Load Mod button)."""

    resolved = Signal(object)
    error = Signal(str)

    def __init__(self, mod_url, parent=None):
        super().__init__(parent)
        self._mod_url = mod_url

    def run(self):
        try:
            portal = FactorioPortalAPI()
            # Extract mod name from URL or treat input as a bare mod name
            m = re.search(r'/mod/([^/?&\s]+)', self._mod_url)
            mod_name = m.group(1) if m else self._mod_url.strip()
            info = portal.get_mod(mod_name)
            self.resolved.emit(info)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: SearchWorker  (500 ms debounce on URL field)
# ---------------------------------------------------------------------------

class SearchWorker(QThread):
    """QThread that searches the portal for mods matching a query string."""

    result = Signal(list, int, int, int)   # (results, token, page, total_pages)
    error = Signal(str)

    def __init__(self, query: str, category: str = "", version: str = "",
                 page: int = 1, token: int = 0, parent=None):
        super().__init__(parent)
        self._query    = query
        self._category = category
        self._version  = version
        self._page     = page
        self._token    = token

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            portal = FactorioPortalAPI()
            if self.isInterruptionRequested():
                return
            results, cur_page, total_pages = portal.search_mods(
                self._query, limit=20,
                category=self._category,
                version=self._version,
                page=self._page,
            )
            if not self.isInterruptionRequested():
                self.result.emit(results, self._token, cur_page, total_pages)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: CategoryBrowseWorker
# ---------------------------------------------------------------------------

class CategoryBrowseWorker(QThread):
    """QThread that fetches portal mods by category."""

    result = Signal(list, int, int, int)   # (results, token, page, total_pages)
    error = Signal(str)

    def __init__(self, category: str, version: str = "", page: int = 1,
                 token: int = 0, parent=None):
        super().__init__(parent)
        self._category = category
        self._version  = version
        self._page     = page
        self._token    = token

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            portal = FactorioPortalAPI()
            if self.isInterruptionRequested():
                return
            results, cur_page, total_pages = portal.search_mods(
                "", limit=20,
                category=self._category,
                version=self._version,
                page=self._page,
            )
            if not self.isInterruptionRequested():
                self.result.emit(results, self._token, cur_page, total_pages)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Version comparison helper
# ---------------------------------------------------------------------------

def _version_lt(v1: str, v2: str) -> bool:
    """Return True if version string v1 is strictly older than v2."""
    from itertools import zip_longest
    try:
        p1 = [int(x) for x in v1.split(".")]
        p2 = [int(x) for x in v2.split(".")]
        for a, b in zip_longest(p1, p2, fillvalue=0):
            if a < b:
                return True
            if a > b:
                return False
        return False
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# ModBrowseCard — clickable card shown in the browse grid
# ---------------------------------------------------------------------------

class ModBrowseCard(QFrame):
    """Single card in the mod-browse grid.

    Emits clicked(mod_name: str) when the user clicks anywhere on the card.
    """

    clicked = Signal(str)

    def __init__(self, entry: dict, installed_versions: dict | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("modBrowseCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mod_name = entry.get("name", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # Title + category chip + status badge row
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        title_lbl = QLabel(entry.get("title") or entry.get("name", ""))
        title_lbl.setObjectName("modCardTitle")
        title_lbl.setWordWrap(False)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_row.addWidget(title_lbl, stretch=1)

        cat = (entry.get("category") or "").replace("-", " ").title()
        if cat:
            cat_lbl = QLabel(cat)
            cat_lbl.setObjectName("modCardCategory")
            title_row.addWidget(cat_lbl)

        # Inline status badge — placed after category chip to avoid overlap
        if installed_versions is not None:
            inst_ver = installed_versions.get(self._mod_name)
            if inst_ver is not None:
                releases = entry.get("releases") or []
                portal_ver = releases[-1].get("version", "") if releases else ""
                if portal_ver and _version_lt(inst_ver, portal_ver):
                    badge_text, badge_name = "Update", "modCardUpdate"
                else:
                    badge_text, badge_name = "Installed", "modCardInstalled"
                badge_lbl = QLabel(badge_text)
                badge_lbl.setObjectName(badge_name)
                title_row.addWidget(badge_lbl)

        layout.addLayout(title_row)

        # Meta row: author · N downloads
        meta_parts = []
        owner = entry.get("owner", "")
        if owner:
            meta_parts.append(f"by {owner}")
        dl = entry.get("downloads_count", 0)
        if dl:
            meta_parts.append(f"{dl:,}\u2193")
        meta_lbl = QLabel("  \u00b7  ".join(meta_parts))
        meta_lbl.setObjectName("modCardMeta")
        layout.addWidget(meta_lbl)

        # Summary (2 lines max)
        summary = (entry.get("summary") or "")[:160]
        if summary:
            summ_lbl = QLabel(summary)
            summ_lbl.setObjectName("modCardSummary")
            summ_lbl.setWordWrap(True)
            summ_lbl.setMaximumHeight(40)
            layout.addWidget(summ_lbl)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._mod_name)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# DownloaderTab — main QWidget
# ---------------------------------------------------------------------------

_LEVEL_COLORS: Dict[str, str] = {
    "DEBUG":    "#b0b0b0",
    "INFO":     "#e0e0e0",
    "WARNING":  "#ffad00",
    "ERROR":    "#d13438",
    "CRITICAL": "#d13438",
    "SUCCESS":  "#4ec952",
}

_MOD_STATUS_COLORS: Dict[str, str] = {
    "Preparing...":   "#b0b0b0",
    "Downloading...": "#0078d4",
    "✓ Downloaded":   "#4ec952",
    "✗ Failed":       "#d13438",
}


class DownloaderTab(QWidget):
    """Qt UI for mod downloader."""

    def __init__(self, status_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.status_manager = status_manager
        self.notification_manager: Optional[NotificationManager] = None
        self._queue_controller = None    # injected by MainWindow after construction
        self._log_bridge = None          # injected by MainWindow after construction
        self._active_jobs: dict = {}     # op_id → DownloadCoordinatorJob
        self._search_worker  = None      # keeps SearchWorker alive until done
        self._resolve_worker = None      # keeps ResolveWorker alive until done
        self._active_worker  = None      # keeps DownloadWorker alive (legacy fallback)
        self._browse_worker  = None      # keeps CategoryBrowseWorker alive until done
        self._request_token  = 0         # incremented on every new search/browse request
        self._current_query    = ""
        self._current_category = ""
        self._current_version  = ""
        self._current_page     = 1
        self._total_pages      = 1
        self._initial_load_done = False
        self._opt_dep_checkboxes: list = []  # per-load optional dep checkboxes
        self._installed_mod_names: dict = {}  # mod_name → installed version string
        self._last_results: list = []         # last grid results (for badge refresh)
        self._setup_ui()
        self._restore_config()

    # ------------------------------------------------------------------
    # NotificationManager interface (called by MainWindow)
    # ------------------------------------------------------------------

    def set_notification_manager(self, manager: NotificationManager) -> None:
        self.notification_manager = manager

    def set_queue_controller(self, controller) -> None:
        """Inject the shared QueueController (called by MainWindow)."""
        self._queue_controller = controller
        # Wire the inline strip to the controller
        if hasattr(self, "_queue_strip"):
            controller.queue_changed.connect(
                lambda ops: self._queue_strip.update_from_operations(ops)
            )
        controller.queue_changed.connect(self._on_queue_progress)

    def set_log_bridge(self, bridge) -> None:
        """Inject the LogSignalBridge so job messages appear in the Logs tab (called by MainWindow)."""
        self._log_bridge = bridge

    def _notify(
        self,
        message: str,
        notif_type: str = "info",
        duration_ms: int = -1,
        actions=None,
        event_key: str | None = None,
    ) -> None:
        if self.notification_manager is not None:
            self.notification_manager.show(
                message,
                notification_type=notif_type,
                duration_ms=duration_ms,
                actions=actions,
                event_key=event_key,
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        from .styles.tokens import SIDE_PANEL_WIDTH

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page header zone
        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        page_title = QLabel("Downloader")
        page_title.setObjectName("pageTitle")
        header_layout.addWidget(page_title)
        header_layout.addStretch()

        self._refresh_btn = QPushButton("\u21bb")
        self._refresh_btn.setObjectName("refreshButton")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setToolTip("Refresh results (F5)")
        self._refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self._refresh_btn)

        root.addWidget(header)

        # Body splitter: browse panel (left) + detail/download panel (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        root.addWidget(splitter, stretch=1)

        # ── LEFT COLUMN: browse ────────────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(8)

        # 1. Search / URL input row
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "Search by name or paste URL (e.g. https://mods.factorio.com/mod/…)"
        )
        self.url_edit.textChanged.connect(self._on_url_changed)
        self.load_btn = QPushButton("Load Mod")
        self.load_btn.clicked.connect(self._on_load_mod)
        url_row.addWidget(self.url_edit, stretch=1)
        url_row.addWidget(self.load_btn)
        left_layout.addLayout(url_row)

        # 2. Category chips (always visible below the search bar)
        self._chips_bar = CategoryChipsBar()
        self._chips_bar.category_selected.connect(self._on_category_selected)
        left_layout.addWidget(self._chips_bar)

        # 3. Version filter chips
        self._version_bar = VersionFilterBar()
        self._version_bar.version_selected.connect(self._on_version_selected)
        left_layout.addWidget(self._version_bar)

        # 4. Scrollable grid of mod cards
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._grid_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setContentsMargins(4, 0, 4, 0)
        # Two equal-width columns
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)
        self._grid_scroll.setWidget(self._grid_container)
        left_layout.addWidget(self._grid_scroll, stretch=1)

        # 5. Pagination bar
        pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(pagination_widget)
        pagination_layout.setContentsMargins(0, 4, 0, 4)
        pagination_layout.setSpacing(8)

        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.setObjectName("paginationBtn")
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._on_prev_page)
        pagination_layout.addWidget(self._prev_btn)

        pagination_layout.addStretch()

        self._page_lbl = QLabel("Page 1 of 1")
        self._page_lbl.setObjectName("paginationLabel")
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self._page_lbl)

        pagination_layout.addStretch()

        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("paginationBtn")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._on_next_page)
        pagination_layout.addWidget(self._next_btn)

        left_layout.addWidget(pagination_widget)

        splitter.addWidget(left_widget)
        splitter.setStretchFactor(0, 1)

        # ── RIGHT PANEL: detail + download workflow ────────────────────
        right_frame = QFrame()
        right_frame.setObjectName("sidePanel")
        right_frame.setMinimumWidth(SIDE_PANEL_WIDTH)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(8, 12, 8, 8)
        right_layout.setSpacing(6)

        side_hdr = QLabel("Selected Mod")
        side_hdr.setObjectName("depsHeader")
        right_layout.addWidget(side_hdr)

        # ── Scrollable detail area ─────────────────────────────────────
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._detail_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _detail_container = QWidget()
        _detail_vbox = QVBoxLayout(_detail_container)
        _detail_vbox.setContentsMargins(0, 0, 4, 0)
        _detail_vbox.setSpacing(0)

        # Empty-state placeholder
        self._no_mod_lbl = QLabel("Search for a mod or paste\na URL to get started.")
        self._no_mod_lbl.setObjectName("modMeta")
        self._no_mod_lbl.setWordWrap(True)
        self._no_mod_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._no_mod_lbl.setContentsMargins(4, 8, 4, 0)
        _detail_vbox.addWidget(self._no_mod_lbl)

        # Mod detail card (hidden until a mod is resolved)
        self._mod_card = QFrame()
        self._mod_card.setObjectName("infoCard")
        self._mod_card.setVisible(False)
        card_vbox = QVBoxLayout(self._mod_card)
        card_vbox.setContentsMargins(10, 8, 10, 10)
        card_vbox.setSpacing(4)

        title_row = QHBoxLayout()
        self.info_title_lbl = QLabel("")
        self.info_title_lbl.setObjectName("modTitle")
        self.info_title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.info_title_lbl.setWordWrap(True)
        self.info_author_lbl = QLabel("")
        self.info_author_lbl.setObjectName("modAuthor")
        self.info_author_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.info_author_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        title_row.addWidget(self.info_title_lbl, stretch=1)
        title_row.addWidget(self.info_author_lbl)
        card_vbox.addLayout(title_row)

        self.info_meta_lbl = QLabel("")
        self.info_meta_lbl.setObjectName("modMeta")
        self.info_meta_lbl.setTextFormat(Qt.TextFormat.PlainText)
        card_vbox.addWidget(self.info_meta_lbl)

        self.info_summary_lbl = QLabel("")
        self.info_summary_lbl.setObjectName("modSummary")
        self.info_summary_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.info_summary_lbl.setWordWrap(True)
        self.info_summary_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        card_vbox.addWidget(self.info_summary_lbl)

        self._dep_divider = QFrame()
        self._dep_divider.setObjectName("depDivider")
        self._dep_divider.setFrameShape(QFrame.Shape.HLine)
        card_vbox.addWidget(self._dep_divider)

        self.deps_hdr = QLabel("Dependencies")
        self.deps_hdr.setObjectName("depsHeader")
        card_vbox.addWidget(self.deps_hdr)

        # Dynamic deps container — cleared and rebuilt each mod load
        self._deps_widget = QWidget()
        self._deps_layout = QVBoxLayout(self._deps_widget)
        self._deps_layout.setContentsMargins(0, 2, 0, 0)
        self._deps_layout.setSpacing(2)
        card_vbox.addWidget(self._deps_widget)

        # Conflict warning section (hidden until a loaded mod has installed conflicts)
        self._conflict_section = QFrame()
        self._conflict_section.setObjectName("conflictSection")
        self._conflict_layout = QVBoxLayout(self._conflict_section)
        self._conflict_layout.setContentsMargins(8, 6, 8, 6)
        self._conflict_layout.setSpacing(4)
        self._conflict_section.setVisible(False)
        card_vbox.addWidget(self._conflict_section)

        _detail_vbox.addWidget(self._mod_card)
        _detail_vbox.addStretch(1)
        self._detail_scroll.setWidget(_detail_container)
        right_layout.addWidget(self._detail_scroll, stretch=1)

        # ── Fixed bottom: folder + download + queue strip + progress ──
        folder_row = QHBoxLayout()
        folder_label = QLabel("Folder:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("Select mods folder…")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse)
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(browse_btn)
        right_layout.addLayout(folder_row)

        self.download_btn = QPushButton("Download Mods")
        self.download_btn.setObjectName("accentButton")
        self.download_btn.setEnabled(False)
        self.download_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.download_btn.clicked.connect(self._on_download)
        right_layout.addWidget(self.download_btn)

        # Inline queue strip (between Download button and progress console)
        self._queue_strip = QueueStrip(source_filter=OperationSource.DOWNLOADER)
        self._queue_strip.open_queue_requested.connect(self._on_open_queue_requested)
        right_layout.addWidget(self._queue_strip)

        # Progress area (hidden until download starts)
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Code", 9))
        self.console.setFixedHeight(90)
        self.console.setPlaceholderText("Download progress will appear here…")
        prog_layout.addWidget(self.console)

        right_layout.addWidget(self._progress_widget)

        splitter.addWidget(right_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, SIDE_PANEL_WIDTH])

        # Debounce timer (500 ms)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._perform_search)

        # Refresh badges whenever the mods folder path changes
        self.folder_edit.textChanged.connect(self._on_folder_changed)

    def _restore_config(self):
        saved = config.get("mods_folder", "")
        if saved:
            self.folder_edit.setText(str(saved))

    def refresh(self) -> None:
        """Re-fetch portal results for the current query/category/version and re-scan installed."""
        self._fire_browse(
            self._current_query,
            self._current_category,
            self._current_version,
            self._current_page,
        )

    def _on_folder_changed(self, _path: str) -> None:
        """Refresh installed-state badges when the mods folder path changes."""
        if self._last_results:
            self._populate_grid(self._last_results)

    # ------------------------------------------------------------------
    # Progress console
    # ------------------------------------------------------------------

    def _append_console(self, message, level="INFO"):
        """Append HTML-escaped, color-coded line to the progress console."""
        color = _LEVEL_COLORS.get(level.upper(), "#e0e0e0")
        safe = html_lib.escape(message)
        self.console.append(f'<span style="color:{color};">{safe}</span>')
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Category chip handler
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Auto-load on first show
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not self._initial_load_done:
            self._initial_load_done = True
            QTimer.singleShot(800, lambda: self._fire_browse("", "", "", 1))

    # ------------------------------------------------------------------
    # Core browse dispatcher
    # ------------------------------------------------------------------

    def _fire_browse(self, query: str, category: str, version: str, page: int) -> None:
        """Start a new browse/search worker, cancelling any running one."""
        for w in (self._search_worker, self._browse_worker):
            if w is not None and w.isRunning():
                w.requestInterruption()
                w.quit()
                w.wait()

        self._current_query    = query
        self._current_category = category
        self._current_version  = version
        self._current_page     = page
        self._request_token   += 1
        token = self._request_token

        self._show_grid_status("Loading\u2026")

        if hasattr(self, "_refresh_btn"):
            self._refresh_btn.setEnabled(False)

        if query:
            worker = SearchWorker(
                query, category=category, version=version, page=page,
                token=token, parent=self,
            )
            self._search_worker = worker
        else:
            worker = CategoryBrowseWorker(
                category, version=version, page=page,
                token=token, parent=self,
            )
            self._browse_worker = worker

        worker.result.connect(self._on_search_result)
        worker.error.connect(lambda e: self._show_grid_status(f"Error: {e}"))
        worker.start()

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    def _clear_grid(self) -> None:
        """Remove all widgets from the browse grid."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_grid_status(self, msg: str) -> None:
        """Clear grid and show a centred status label spanning both columns."""
        self._clear_grid()
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setObjectName("modMeta")
        self._grid_layout.addWidget(lbl, 0, 0, 1, 2)
        self._grid_layout.setRowStretch(0, 0)
        self._grid_layout.setRowStretch(1, 1)

    def _populate_grid(self, results: list) -> None:
        """Fill the browse grid with ModBrowseCard widgets."""
        self._last_results = results
        folder = self.folder_edit.text().strip()
        if folder:
            self._installed_mod_names = self._scan_installed_mod_names(folder)
        self._clear_grid()
        if not results:
            self._show_grid_status("No mods found.")
            return
        for i, entry in enumerate(results):
            row, col = divmod(i, 2)
            card = ModBrowseCard(
                entry,
                installed_versions=self._installed_mod_names if self._installed_mod_names else None,
                parent=self._grid_container,
            )
            card.clicked.connect(self._on_card_clicked)
            self._grid_layout.addWidget(card, row, col)
        # Trailing stretch so cards don't expand vertically
        last_row = (len(results) - 1) // 2 + 1
        self._grid_layout.setRowStretch(last_row, 1)
        self._grid_scroll.verticalScrollBar().setValue(0)

    def _update_pagination_ui(self) -> None:
        self._page_lbl.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    # ------------------------------------------------------------------
    # Category chip handler
    # ------------------------------------------------------------------

    def _on_category_selected(self, category: str) -> None:
        """Fire a portal browse query for the selected category chip."""
        # Clear URL bar silently when browsing by category
        self.url_edit.blockSignals(True)
        self.url_edit.clear()
        self.url_edit.blockSignals(False)
        self._reset_mod_detail()
        self._fire_browse("", category, self._current_version, 1)

    def _on_version_selected(self, version: str) -> None:
        """Re-fire current browse/search with the new version filter."""
        query = self.url_edit.text().strip()
        if query and not query.startswith("http") and "mods.factorio.com" not in query:
            self._fire_browse(query, "", version, 1)
        else:
            self._fire_browse("", self._current_category, version, 1)

    # ------------------------------------------------------------------
    # URL / search handlers
    # ------------------------------------------------------------------

    def _on_url_changed(self, text):
        self._search_timer.stop()
        stripped = text.strip()
        if not stripped:
            # Revert to category browse
            self._fire_browse("", self._current_category, self._current_version, 1)
            self._reset_mod_detail()
            return
        # Skip live search when the field already contains a full URL
        if stripped.startswith("http") or "mods.factorio.com" in stripped:
            return
        # Reset category chips to "All" when the user is typing a search term
        self._chips_bar.select_chip("All")
        self._search_timer.start()

    def _perform_search(self):
        """Run after 500 ms debounce: fetch mod info in background."""
        query = self.url_edit.text().strip()
        if not query:
            return
        self._notify("Searching mods...", event_key="search_running")
        self._fire_browse(query, "", self._current_version, 1)

    @Slot(list, int, int, int)
    def _on_search_result(self, results: list, token: int, page: int, total_pages: int):
        if token != self._request_token:
            return
        self._current_page  = page
        self._total_pages   = total_pages
        self._search_worker = None
        self._browse_worker = None
        if hasattr(self, "_refresh_btn"):
            self._refresh_btn.setEnabled(True)
        self._update_pagination_ui()
        self._populate_grid(results)

    def _on_card_clicked(self, mod_name: str) -> None:
        """Handle card click: populate right panel with mod detail."""
        self.url_edit.blockSignals(True)
        self.url_edit.setText(f"https://mods.factorio.com/mod/{mod_name}")
        self.url_edit.blockSignals(False)
        self._on_load_mod()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _on_prev_page(self) -> None:
        if self._current_page > 1:
            self._fire_browse(
                self._current_query, self._current_category,
                self._current_version, self._current_page - 1,
            )

    def _on_next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._fire_browse(
                self._current_query, self._current_category,
                self._current_version, self._current_page + 1,
            )

    def _on_load_mod(self):
        url = self.url_edit.text().strip()
        if not url:
            self._notify("Please enter a mod URL or name.", "error")
            return
        self._notify("Resolving mod details...", event_key="mod_resolve")
        self.load_btn.setEnabled(False)
        worker = ResolveWorker(url, parent=self)
        self._resolve_worker = worker
        worker.resolved.connect(self._advance_to_stage_2)
        worker.error.connect(self._on_resolve_error)
        worker.finished.connect(lambda: self.load_btn.setEnabled(True))
        worker.start()

    @Slot(object)
    def _populate_mod_info(self, info):
        title   = info.get("title") or info.get("name", "")
        author  = info.get("owner", "")
        summary = info.get("summary", "")
        downloads = info.get("downloads_count", 0)

        releases = info.get("releases", [])
        version         = ""
        factorio_version = ""
        if releases:
            latest = releases[-1]
            version          = latest.get("version", "")
            factorio_version = latest.get("factorio_version", "")

        self.info_title_lbl.setText(title)
        self.info_author_lbl.setText(f"by {author}" if author else "")

        meta_parts = []
        if version:
            meta_parts.append(f"v{version}")
        if downloads:
            meta_parts.append(f"{downloads:,} downloads")
        if factorio_version:
            meta_parts.append(f"Factorio {factorio_version}")
        self.info_meta_lbl.setText("  \u00b7  ".join(meta_parts))

        self.info_summary_lbl.setText(summary[:240] if summary else "")
        self.info_summary_lbl.setVisible(bool(summary))

        # Parse and display dependencies
        req, opt, base, incompat = self._parse_deps(info)

        # Rebuild dep rows from scratch
        while self._deps_layout.count():
            item = self._deps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._opt_dep_checkboxes = []

        def _dep_section(section_title, names, prefix="\u2192", obj_name="depRow"):
            if not names:
                return
            hdr = QLabel(section_title)
            hdr.setObjectName("depSectionHdr")
            self._deps_layout.addWidget(hdr)
            for name in names:
                lbl = QLabel(f"  {prefix}  {name}")
                lbl.setObjectName(obj_name)
                lbl.setTextFormat(Qt.TextFormat.PlainText)
                lbl.setWordWrap(True)
                self._deps_layout.addWidget(lbl)

        _dep_section("Required", req, "\u2192", "depRow")

        if opt:
            hdr = QLabel("Optional  \u2014  check to include")
            hdr.setObjectName("depSectionHdr")
            self._deps_layout.addWidget(hdr)
            for name in opt:
                cb = QCheckBox(name)
                cb.setObjectName("depOptCheckbox")
                self._deps_layout.addWidget(cb)
                self._opt_dep_checkboxes.append(cb)

        _dep_section("Base / Expansion", base, "\u25c6", "depRow")
        _dep_section("Incompatible", incompat, "\u2715", "depRowIncompat")

        any_deps = bool(req or opt or base or incompat)
        self.deps_hdr.setVisible(any_deps)
        self._dep_divider.setVisible(any_deps)
        self._deps_widget.setVisible(any_deps)

        # Build conflict panel for incompatible mods that are already installed
        self._refresh_conflict_section(incompat)

        self._mod_card.setVisible(True)
        self._no_mod_lbl.setVisible(False)
        self._resolve_worker = None

    def _refresh_conflict_section(self, incompat_names: list) -> None:
        """Rebuild the inline conflict warning panel based on installed mods."""
        # Clear existing rows
        while self._conflict_layout.count():
            item = self._conflict_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Only show conflicts for mods that are physically installed
        conflicts = [
            name for name in incompat_names
            if name in self._installed_mod_names
        ]
        if not conflicts:
            self._conflict_section.setVisible(False)
            return

        warn_hdr = QLabel("\u26a0\ufe0f  Installed Conflicts")
        warn_hdr.setObjectName("conflictHeader")
        self._conflict_layout.addWidget(warn_hdr)

        for mod_name in conflicts:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(mod_name)
            lbl.setObjectName("conflictModName")
            row.addWidget(lbl, stretch=1)

            disable_btn = QPushButton("Disable")
            disable_btn.setObjectName("conflictDisableBtn")
            disable_btn.setFlat(True)
            # Capture name in default arg to avoid late-binding
            disable_btn.clicked.connect(
                lambda _checked=False, n=mod_name: self._on_conflict_disable(n)
            )
            row.addWidget(disable_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("destructiveButton")
            remove_btn.setFlat(True)
            remove_btn.clicked.connect(
                lambda _checked=False, n=mod_name: self._on_conflict_remove(n)
            )
            row.addWidget(remove_btn)

            container = QWidget()
            container.setLayout(row)
            self._conflict_layout.addWidget(container)

        self._conflict_section.setVisible(True)

    def _on_conflict_disable(self, mod_name: str) -> None:
        """Disable a conflicting mod via mod-list.json (does not remove the file)."""
        folder = self.folder_edit.text().strip()
        if not folder:
            self._notify("No mods folder selected.", "error")
            return
        store = ModListStore(Path(folder))
        states = store.load()
        states[mod_name] = False
        store.save(states)
        self._notify(f"{mod_name} disabled.", "info")
        # Re-scan and rebuild panel — mod file still exists but is marked disabled
        # It stays in installed names, so keep the row but reflect the change
        self._refresh_conflict_section(
            [n for n in self._installed_mod_names
             if n in {w.text() for w in self._conflict_section.findChildren(QLabel, "conflictModName")}]
        )

    def _on_conflict_remove(self, mod_name: str) -> None:
        """Physically remove a conflicting mod's zip file from the mods folder."""
        folder = self.folder_edit.text().strip()
        if not folder:
            self._notify("No mods folder selected.", "error")
            return
        p = Path(folder)
        removed = 0
        for zf in list(p.glob(f"{mod_name}_*.zip")):
            try:
                zf.unlink()
                removed += 1
            except OSError as exc:
                self._notify(f"Could not remove {zf.name}: {exc}", "error")
        if removed:
            self._notify(f"{mod_name} removed ({removed} file(s)).", "success")
        # Refresh installed names and rebuild panel
        self._installed_mod_names = self._scan_installed_mod_names(folder)
        # Collect remaining conflict mod names from UI labels before rebuild
        remaining = [
            n for n in self._installed_mod_names
            if n in {w.text() for w in self._conflict_section.findChildren(QLabel, "conflictModName")}
            and n != mod_name
        ]
        self._refresh_conflict_section(remaining)

    @staticmethod
    def _scan_installed_mod_names(folder: str) -> dict:
        """Return dict of {mod_name: installed_version} from *.zip files in folder."""
        if not folder:
            return {}
        p = Path(folder)
        if not p.is_dir():
            return {}
        result: dict = {}
        for f in p.glob("*.zip"):
            stem = f.stem
            if "_" in stem:
                name, ver = stem.rsplit("_", 1)
                result[name] = ver
            else:
                result[stem] = ""
        return result

    def _advance_to_stage_2(self, mod_info: object) -> None:
        """Populate mod detail card in right panel and enable download."""
        # Refresh installed mod list so conflict panel is up to date
        self._installed_mod_names = self._scan_installed_mod_names(
            self.folder_edit.text().strip()
        )
        # Reset stale progress area whenever there are no active downloads
        if not self._active_jobs:
            self._progress_widget.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setProperty("completed", "")
            self.progress_bar.style().unpolish(self.progress_bar)
            self.progress_bar.style().polish(self.progress_bar)
        self._populate_mod_info(mod_info)
        self._mod_card.setVisible(True)
        self._no_mod_lbl.setVisible(False)
        self.download_btn.setEnabled(True)
        self._restore_config()

    def _reset_mod_detail(self) -> None:
        """Hide mod detail card and disable download controls."""
        self._mod_card.setVisible(False)
        self._no_mod_lbl.setVisible(True)
        self.download_btn.setEnabled(False)
        self._progress_widget.setVisible(False)

    @Slot(str)
    def _on_resolve_error(self, error_msg: str) -> None:
        self._notify(f"Could not resolve mod: {error_msg}", "error", event_key="resolve_error")

    # ------------------------------------------------------------------
    # Browse folder
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

    # ------------------------------------------------------------------
    # Dependency parser (runs on the main thread from raw API dict)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_deps(info):
        """Return (required, optional, base, incompatible) lists from raw portal dict."""
        from ..core.mod import FACTORIO_EXPANSIONS
        releases = info.get("releases", [])
        if not releases:
            return [], [], [], []
        deps_raw = releases[-1].get("info_json", {}).get("dependencies", [])
        required, optional, base, incompatible = [], [], [], []
        for dep in deps_raw:
            dep = dep.strip()
            if not dep or dep == "base" or dep.startswith("base "):
                continue
            if dep.startswith("!"):
                name = re.split(r"[\s><=!]", dep[1:].strip())[0]
                if name:
                    incompatible.append(name)
            elif dep.startswith("(?)") or dep.startswith("?"):
                clean = dep.replace("(?)", "").replace("?", "").strip()
                name  = re.split(r"[\s><=!]", clean)[0]
                if name in FACTORIO_EXPANSIONS:
                    base.append(name)
                elif name:
                    optional.append(name)
            else:
                name = re.split(r"[\s><=!]", dep)[0]
                if name in FACTORIO_EXPANSIONS:
                    base.append(name)
                elif name:
                    required.append(name)
        return required, optional, base, incompatible

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_open_queue_requested(self) -> None:
        """Forward queue-strip 'Open Queue' clicks to the main window."""
        main_win = self.window()
        if hasattr(main_win, "open_queue_drawer"):
            main_win.open_queue_drawer()

    def _on_download(self):
        url = self.url_edit.text().strip()
        folder = self.folder_edit.text().strip()

        if not url:
            self._notify("Please enter a mod URL or name.", "error")
            return
        if not folder:
            self._notify("Please select a mods folder.", "error")
            return
        online, _offline_reason = is_online()
        if not online:
            self._notify("You appear to be offline.", "error")
            return

        selected_optionals = [cb.text() for cb in self._opt_dep_checkboxes if cb.isChecked()]

        # ── Queue-backed path ──────────────────────────────────────────
        if self._queue_controller is not None:
            import re as _re
            m = _re.search(r"/mod/([^/?&\s]+)", url)
            mod_name = m.group(1) if m else url.strip()
            max_workers = config.get("max_workers", 4)

            op = QueueOperation(
                source=OperationSource.DOWNLOADER,
                kind=OperationKind.DOWNLOAD,
                label=f"Download {mod_name}\u2026",
            )
            job = DownloadCoordinatorJob(
                op, mod_name, selected_optionals, folder,
                max_workers=max_workers, parent=self,
            )
            job.log_message.connect(self._append_console)
            if self._log_bridge is not None:
                job.log_message.connect(self._log_bridge.log_record)
            job.finished_op.connect(self._on_coordinator_finished)
            self._active_jobs[op.id] = job

            self._queue_controller.batch_enqueue([op])
            self._queue_controller.start_next()
            job.start(self._queue_controller)

            # Show progress console
            self._progress_widget.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setProperty("completed", "false")
            self.progress_bar.style().unpolish(self.progress_bar)
            self.progress_bar.style().polish(self.progress_bar)
            self.console.clear()

            self._notify(f"Resolving {mod_name}\u2026", "info")
            return

        # ── Legacy fallback (no queue controller wired) ────────────────
        self.download_btn.setEnabled(False)
        self._progress_widget.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setProperty("completed", "false")
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)
        self.console.clear()

        worker = DownloadWorker(url, folder, False, extra_mods=selected_optionals, parent=self)
        self._active_worker = worker
        worker.progress.connect(self._on_progress)
        worker.mod_status.connect(self._on_mod_status)
        worker.log_message.connect(self._append_console)
        if self._log_bridge is not None:
            worker.log_message.connect(self._log_bridge.log_record)
        worker.finished.connect(self._on_download_finished)
        worker.start()

    @Slot(list)
    def _on_queue_progress(self, operations: list) -> None:
        """Mirror queue-controller state into the inline progress widget."""
        for op in operations:
            if op.id not in self._active_jobs:
                continue

            # Update progress bar while running
            if op.state == OperationState.RUNNING:
                if op.progress is not None:
                    self.progress_bar.setValue(op.progress)

            elif op.state == OperationState.COMPLETED:
                self.progress_bar.setValue(100)
                self.progress_bar.setProperty("completed", "true")
                self.progress_bar.style().unpolish(self.progress_bar)
                self.progress_bar.style().polish(self.progress_bar)

            elif op.state == OperationState.FAILED:
                short = op.failure.short_description if op.failure else "Download failed"
                self._notify(f"\u2717 {short}", "error")
                if self.status_manager:
                    self.status_manager.push_status("Download failed", "error")

            elif op.state == OperationState.CANCELED:
                self._notify("Download canceled", "info")

        # Hide progress widget once no active jobs remain
        if not self._active_jobs:
            self._progress_widget.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setProperty("completed", "")
            self.progress_bar.style().unpolish(self.progress_bar)
            self.progress_bar.style().polish(self.progress_bar)

    @Slot(str)
    def _on_coordinator_finished(self, op_id: str) -> None:
        """Called when a DownloadCoordinatorJob completes (any outcome)."""
        job = self._active_jobs.pop(op_id, None)
        if job is None:
            return

        # Determine final state from the queue controller snapshot
        state = OperationState.COMPLETED
        if self._queue_controller is not None:
            for op in self._queue_controller._operations:  # noqa: SLF001
                if op.id == op_id:
                    state = op.state
                    break

        if state == OperationState.COMPLETED:
            self._notify("\u2713 Download complete", "success")
            if self.status_manager:
                self.status_manager.push_status("Download complete", "success")
            # Refresh badges so newly downloaded mod shows "Installed"
            if self._last_results:
                self._populate_grid(self._last_results)
        elif state == OperationState.FAILED:
            if self.status_manager:
                self.status_manager.push_status("Download failed", "error")
        # CANCELED already notified via _on_queue_progress

        if not self._active_jobs:
            self._progress_widget.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setProperty("completed", "")
            self.progress_bar.style().unpolish(self.progress_bar)
            self.progress_bar.style().polish(self.progress_bar)

    @Slot(int, int)
    def _on_progress(self, completed, total):
        if total > 0:
            pct = int(completed / total * 100)
            self.progress_bar.setValue(pct)
            self._notify(
                f"Downloading: {completed}/{total} mods ({pct}%)",
                event_key="download_progress",
            )
            if self.status_manager:
                self.status_manager.push_status(
                    f"Downloading: {completed}/{total} mods ({pct}%)", "info"
                )

    @Slot(str, str)
    def _on_mod_status(self, mod_name, status_text):
        self._append_console(f"{mod_name}: {status_text}", "INFO")

    @Slot(bool, list)
    def _on_download_finished(self, all_succeeded, failed):
        # Always re-enable (PREP-03 fix — re-enable on error too)
        self.download_btn.setEnabled(True)
        self._active_worker = None

        if all_succeeded:
            self.progress_bar.setValue(100)
            self.progress_bar.setProperty("completed", "true")
            self.progress_bar.style().unpolish(self.progress_bar)
            self.progress_bar.style().polish(self.progress_bar)
            self._notify("✓ Download complete", "success")
            if self.status_manager:
                self.status_manager.push_status("Download complete", "success")
        else:
            if failed:
                self._notify(f"✗ Failed to download: {', '.join(failed)}", "error")
            else:
                self._notify("✗ Download failed.", "error")
            if self.status_manager:
                self.status_manager.push_status("Download failed", "error")