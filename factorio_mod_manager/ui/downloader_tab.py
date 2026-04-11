"""Downloader tab UI — Qt implementation."""
from __future__ import annotations

import html as html_lib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import ModDownloader
from ..core.portal import FactorioPortalAPI, PortalAPIError
from ..utils import config, validate_mod_url, format_file_size, is_online
from .widgets import NotificationManager
from .filter_sort_bar import CategoryChipsBar


# ---------------------------------------------------------------------------
# Worker: DownloadWorker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """QThread that runs ModDownloader.download_mod() and emits typed signals."""

    progress = Signal(int, int)     # (completed_count, total_count)
    mod_status = Signal(str, str)   # (mod_name, status_text)
    log_message = Signal(str, str)  # (message, level_name)
    finished = Signal(bool, list)   # (all_succeeded, failed_mod_names)

    def __init__(self, mod_url, mods_folder, include_optional=False, parent=None):
        super().__init__(parent)
        self._mod_url = mod_url
        self._mods_folder = mods_folder
        self._include_optional = include_optional

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

            # Extract mod name from URL or treat input as a bare mod name
            import re as _re
            m = _re.search(r'/mod/([^/?&\s]+)', self._mod_url)
            mod_name = m.group(1) if m else self._mod_url.strip()

            downloaded, failed = downloader.download_mods(
                [mod_name], include_optional=self._include_optional
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

    result = Signal(list)
    error = Signal(str)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self):
        try:
            portal = FactorioPortalAPI()
            # Request 50 candidates; portal will page_size=50 let us rank properly
            raw: List[dict] = portal.search_mods(self._query, limit=50)
            q = self._query.lower()

            def _rank(entry):
                name  = (entry.get("name")  or "").lower()
                title = (entry.get("title") or "").lower()
                if name == q or title == q:        return 0  # exact
                if name.startswith(q):             return 1  # name prefix
                if title.startswith(q):            return 2  # title prefix
                if q in name:                      return 3  # name contains
                if q in title:                     return 4  # title contains
                return 5                                     # no match

            raw.sort(key=_rank)
            # Drop completely unrelated entries; fall back if nothing matched
            relevant = [e for e in raw if _rank(e) < 5]
            self.result.emit((relevant if relevant else raw)[:8])
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: CategoryBrowseWorker
# ---------------------------------------------------------------------------

class CategoryBrowseWorker(QThread):
    """QThread that fetches portal mods by category."""

    result = Signal(list)
    error = Signal(str)

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self._category = category

    def run(self):
        try:
            portal = FactorioPortalAPI()
            results = portal.search_mods("", limit=20, category=self._category)
            self.result.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


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
        self._search_worker  = None      # keeps SearchWorker alive until done
        self._resolve_worker = None      # keeps ResolveWorker alive until done
        self._active_worker  = None      # keeps DownloadWorker alive until done
        self._browse_worker  = None      # keeps CategoryBrowseWorker alive until done
        self._setup_ui()
        self._restore_config()

    # ------------------------------------------------------------------
    # NotificationManager interface (called by MainWindow)
    # ------------------------------------------------------------------

    def set_notification_manager(self, manager: NotificationManager) -> None:
        self.notification_manager = manager

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

        self.download_btn_header = QPushButton("Download Mods")
        self.download_btn_header.setObjectName("accentButton")
        self.download_btn_header.setEnabled(False)
        self.download_btn_header.clicked.connect(self._on_download)
        header_layout.addWidget(self.download_btn_header)
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

        # 3. Results list — always visible, expands to fill remaining space
        self.search_results_list = QListWidget()
        self.search_results_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.search_results_list.itemClicked.connect(self._on_result_selected)
        self._show_results_placeholder()
        left_layout.addWidget(self.search_results_list, stretch=1)

        splitter.addWidget(left_widget)
        splitter.setStretchFactor(0, 1)

        # ── RIGHT PANEL: detail + download workflow ────────────────────
        right_frame = QFrame()
        right_frame.setObjectName("sidePanel")
        right_frame.setFixedWidth(SIDE_PANEL_WIDTH)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(8, 12, 8, 8)
        right_layout.setSpacing(6)

        side_hdr = QLabel("Selected Mod")
        side_hdr.setObjectName("depsHeader")
        right_layout.addWidget(side_hdr)

        # Empty-state placeholder
        self._no_mod_lbl = QLabel("Search for a mod or paste\na URL to get started.")
        self._no_mod_lbl.setObjectName("modMeta")
        self._no_mod_lbl.setWordWrap(True)
        self._no_mod_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.addWidget(self._no_mod_lbl)

        # Mod detail card (hidden until a mod is resolved)
        self._mod_card = QFrame()
        self._mod_card.setObjectName("infoCard")
        self._mod_card.setVisible(False)
        card_vbox = QVBoxLayout(self._mod_card)
        card_vbox.setContentsMargins(10, 8, 10, 8)
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

        self.deps_required_lbl = QLabel("")
        self.deps_optional_lbl = QLabel("")
        self.deps_base_lbl = QLabel("")
        self.deps_incompat_lbl = QLabel("")
        for dep_lbl in (
            self.deps_required_lbl,
            self.deps_optional_lbl,
            self.deps_base_lbl,
            self.deps_incompat_lbl,
        ):
            dep_lbl.setWordWrap(True)
            dep_lbl.setTextFormat(Qt.TextFormat.PlainText)
            dep_lbl.setVisible(False)
            card_vbox.addWidget(dep_lbl)

        self.deps_required_lbl.setProperty("depType", "required")
        self.deps_optional_lbl.setProperty("depType", "optional")
        self.deps_base_lbl.setProperty("depType", "base")
        self.deps_incompat_lbl.setProperty("depType", "incompatible")

        right_layout.addWidget(self._mod_card)

        # Options + download controls (always present; enabled once mod is loaded)
        self.optional_checkbox = QCheckBox("Include optional dependencies")
        self.optional_checkbox.setEnabled(False)
        right_layout.addWidget(self.optional_checkbox)

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

        # Progress area (hidden until download starts)
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Code", 9))
        self.console.setPlaceholderText("Download progress will appear here…")
        prog_layout.addWidget(self.console, stretch=1)

        right_layout.addWidget(self._progress_widget, stretch=1)

        splitter.addWidget(right_frame)
        splitter.setStretchFactor(1, 0)

        # Debounce timer (500 ms)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._perform_search)

    def _restore_config(self):
        saved = config.get("mods_folder", "")
        if saved:
            self.folder_edit.setText(str(saved))

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

    def _show_results_placeholder(self) -> None:
        """Show browse hint in results list when no results are loaded."""
        self.search_results_list.clear()
        item = QListWidgetItem("Browse by category above or type a mod name to search…")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.search_results_list.addItem(item)

    def _on_category_selected(self, category: str) -> None:
        """Fire a portal browse query for the selected category chip."""
        if self._browse_worker is not None and self._browse_worker.isRunning():
            self._browse_worker.quit()
        # Clear URL bar silently so it's obvious the category is driving the browse
        self.url_edit.blockSignals(True)
        self.url_edit.clear()
        self.url_edit.blockSignals(False)
        # Reset any loaded mod detail
        self._reset_mod_detail()
        worker = CategoryBrowseWorker(category, parent=self)
        self._browse_worker = worker
        worker.result.connect(self._on_search_result)
        worker.error.connect(lambda e: self._notify(f"Category browse failed: {e}", "error"))
        self.search_results_list.clear()
        placeholder = QListWidgetItem("Loading\u2026")
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        self.search_results_list.addItem(placeholder)
        worker.start()

    # ------------------------------------------------------------------
    # URL / search handlers
    # ------------------------------------------------------------------

    def _on_url_changed(self, text):
        self._search_timer.stop()
        stripped = text.strip()
        if not stripped:
            self._show_results_placeholder()
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
        # Show placeholder immediately so the user knows something is happening
        self.search_results_list.clear()
        placeholder = QListWidgetItem("Searching\u2026")
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        self.search_results_list.addItem(placeholder)
        self.search_results_list.setVisible(True)

        worker = SearchWorker(query, parent=self)
        self._search_worker = worker
        worker.result.connect(self._on_search_result)
        worker.error.connect(lambda _e: self._show_results_placeholder())
        worker.start()

    @Slot(list)
    def _on_search_result(self, results: list):
        self.search_results_list.clear()
        if not results:
            self._show_results_placeholder()
            self._search_worker = None
            self._browse_worker = None
            return
        for entry in results:
            name    = entry.get("name", "")
            title   = entry.get("title") or name
            author  = entry.get("owner", "")
            dl      = entry.get("downloads_count", 0)
            display = title if name.lower() in title.lower() else f"{title}  ({name})"
            if author:
                display += f"  by {author}"
            if dl:
                display += f"  \u00b7 {dl:,}\u2193"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.search_results_list.addItem(item)
        self._search_worker = None
        self._browse_worker = None

    def _on_result_selected(self, item: QListWidgetItem):
        mod_name = item.data(Qt.ItemDataRole.UserRole)
        if not mod_name:
            return
        # Block textChanged so the debounce timer doesn't re-trigger search
        self.url_edit.blockSignals(True)
        self.url_edit.setText(f"https://mods.factorio.com/mod/{mod_name}")
        self.url_edit.blockSignals(False)
        # Automatically load the mod detail into the right panel
        self._on_load_mod()

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
        for lbl, prefix, items in (
            (self.deps_required_lbl,  "Required:",     req),
            (self.deps_optional_lbl,  "Optional:",     opt),
            (self.deps_base_lbl,      "Base/Game:",    base),
            (self.deps_incompat_lbl,  "Incompatible:", incompat),
        ):
            if items:
                lbl.setText(f"{prefix} {', '.join(items)}")
                lbl.setVisible(True)
            else:
                lbl.setVisible(False)

        any_deps = bool(req or opt or base or incompat)
        self.deps_hdr.setVisible(any_deps)
        self._dep_divider.setVisible(any_deps)

        self._mod_card.setVisible(True)
        self._no_mod_lbl.setVisible(False)
        self._resolve_worker = None

    @Slot(object)
    def _on_resolved(self, info):
        self._populate_mod_info(info)

    @Slot(object)
    def _advance_to_stage_2(self, mod_info: object) -> None:
        """Populate mod detail card in right panel and enable download."""
        self._populate_mod_info(mod_info)
        self._mod_card.setVisible(True)
        self._no_mod_lbl.setVisible(False)
        self.optional_checkbox.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.download_btn_header.setEnabled(True)
        self._restore_config()

    def _reset_mod_detail(self) -> None:
        """Hide mod detail card and disable download controls."""
        self._mod_card.setVisible(False)
        self._no_mod_lbl.setVisible(True)
        self.optional_checkbox.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.download_btn_header.setEnabled(False)
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

    def _on_download(self):
        url = self.url_edit.text().strip()
        folder = self.folder_edit.text().strip()

        if not url:
            self._notify("Please enter a mod URL or name.", "error")
            return
        if not folder:
            self._notify("Please select a mods folder.", "error")
            return
        if not is_online():
            self._notify("You appear to be offline.", "error")
            return

        # Reset download UI
        self.download_btn.setEnabled(False)
        self.download_btn_header.setEnabled(False)
        self._progress_widget.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setProperty("completed", "false")
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)
        self.console.clear()

        include_optional = self.optional_checkbox.isChecked()
        worker = DownloadWorker(url, folder, include_optional, parent=self)
        self._active_worker = worker
        worker.progress.connect(self._on_progress)
        worker.mod_status.connect(self._on_mod_status)
        worker.log_message.connect(self._append_console)
        worker.finished.connect(self._on_download_finished)
        worker.start()

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
        self.download_btn_header.setEnabled(True)
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
