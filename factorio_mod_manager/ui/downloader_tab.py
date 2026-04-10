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
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import ModDownloader
from ..core.portal import FactorioPortalAPI, PortalAPIError
from ..utils import config, validate_mod_url, format_file_size, is_online
from .widgets import NotificationManager


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

            def _on_mod_status(mod_name, status):
                self.mod_status.emit(mod_name, status)

            downloader.set_overall_progress_callback(_on_progress)
            downloader.set_mod_progress_callback(_on_mod_status)
            success_count, failed = downloader.download_mod(self._mod_url, self._mods_folder)
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
        self._sidebar_labels: Dict[str, QLabel] = {}  # mod_name -> status QLabel
        self._setup_ui()
        self._restore_config()

    # ------------------------------------------------------------------
    # NotificationManager interface (called by MainWindow)
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
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # URL row
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "Enter mod URL or name (e.g. https://mods.factorio.com/mod/…)"
        )
        self.url_edit.textChanged.connect(self._on_url_changed)
        self.load_btn = QPushButton("Load Mod")
        self.load_btn.clicked.connect(self._on_load_mod)
        url_row.addWidget(self.url_edit, stretch=1)
        url_row.addWidget(self.load_btn)
        root.addLayout(url_row)

        # Search results dropdown list (hidden until user types)
        self.search_results_list = QListWidget()
        self.search_results_list.setMaximumHeight(160)
        self.search_results_list.setVisible(False)
        self.search_results_list.itemClicked.connect(self._on_result_selected)
        root.addWidget(self.search_results_list)

        # Mod info panel (shown after resolve)
        self.info_panel = QFrame()
        self.info_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.info_panel.setStyleSheet("QFrame { background: #1e2228; border: 1px solid #3a3f47; border-radius: 4px; }")
        self.info_panel.setVisible(False)
        info_vbox = QVBoxLayout(self.info_panel)
        info_vbox.setContentsMargins(10, 8, 10, 8)
        info_vbox.setSpacing(4)

        title_row = QHBoxLayout()
        self.info_title_lbl = QLabel("")
        self.info_title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #e8e8e8; background: transparent; border: none;")
        self.info_author_lbl = QLabel("")
        self.info_author_lbl.setStyleSheet("color: #9aaab4; font-size: 11px; background: transparent; border: none;")
        self.info_author_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self.info_title_lbl, stretch=1)
        title_row.addWidget(self.info_author_lbl)
        info_vbox.addLayout(title_row)

        self.info_meta_lbl = QLabel("")
        self.info_meta_lbl.setStyleSheet("color: #707070; font-size: 11px; background: transparent; border: none;")
        info_vbox.addWidget(self.info_meta_lbl)

        self.info_summary_lbl = QLabel("")
        self.info_summary_lbl.setWordWrap(True)
        self.info_summary_lbl.setStyleSheet("color: #c0c0c0; font-size: 12px; margin-top: 4px; background: transparent; border: none;")
        self.info_summary_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_vbox.addWidget(self.info_summary_lbl)

        self._dep_divider = QFrame()
        self._dep_divider.setFrameShape(QFrame.Shape.HLine)
        self._dep_divider.setStyleSheet("background: #3a3f47; border: none; max-height: 1px; margin-top: 4px;")
        info_vbox.addWidget(self._dep_divider)

        self.deps_hdr = QLabel("Dependencies")
        self.deps_hdr.setStyleSheet("font-size: 11px; font-weight: bold; color: #9aaab4; background: transparent; border: none; margin-top: 2px;")
        info_vbox.addWidget(self.deps_hdr)

        self.deps_required_lbl = QLabel("")
        self.deps_optional_lbl = QLabel("")
        self.deps_base_lbl     = QLabel("")
        self.deps_incompat_lbl = QLabel("")
        _dep_styles = [
            (self.deps_required_lbl, "#e0e0e0"),
            (self.deps_optional_lbl, "#9aaab4"),
            (self.deps_base_lbl,     "#7ec8e3"),
            (self.deps_incompat_lbl, "#d13438"),
        ]
        for _lbl, _color in _dep_styles:
            _lbl.setWordWrap(True)
            _lbl.setStyleSheet(f"color: {_color}; font-size: 11px; background: transparent; border: none;")
            _lbl.setVisible(False)
            info_vbox.addWidget(_lbl)

        root.addWidget(self.info_panel)

        # Folder row
        folder_row = QHBoxLayout()
        folder_label = QLabel("Mods Folder:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("Select your Factorio mods folder…")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse)
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # Options row
        options_row = QHBoxLayout()
        self.optional_checkbox = QCheckBox("Include optional dependencies")
        options_row.addWidget(self.optional_checkbox)
        options_row.addStretch()
        root.addLayout(options_row)

        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("accentButton")
        self.download_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.download_btn.clicked.connect(self._on_download)
        root.addWidget(self.download_btn)

        # Progress section (QHBoxLayout: left col + right sidebar)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)

        left_col = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        left_col.addWidget(self.progress_bar)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Code", 9))
        self.console.setPlaceholderText("Download progress will appear here…")
        self.console.setMaximumHeight(120)
        left_col.addWidget(self.console)
        progress_row.addLayout(left_col, stretch=1)

        # Right sidebar (fixed 220 px) — per-mod status rows
        self._sidebar_scroll = QScrollArea()
        self._sidebar_scroll.setFixedWidth(220)
        self._sidebar_scroll.setWidgetResizable(True)
        self._sidebar_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._sidebar_inner = QWidget()
        self._sidebar_layout = QVBoxLayout(self._sidebar_inner)
        self._sidebar_layout.setContentsMargins(4, 4, 4, 4)
        self._sidebar_layout.setSpacing(4)
        self._sidebar_layout.addStretch()
        self._sidebar_scroll.setWidget(self._sidebar_inner)
        progress_row.addWidget(self._sidebar_scroll)

        self.progress_bar.setVisible(False)
        self._sidebar_scroll.setVisible(False)

        root.addLayout(progress_row, stretch=1)

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
    # Sidebar helpers
    # ------------------------------------------------------------------

    def _clear_sidebar(self):
        """Remove all per-mod rows from sidebar; clear label map."""
        self._sidebar_labels.clear()
        layout = self._sidebar_layout
        # Remove all items except the trailing addStretch()
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_sidebar_row(self, mod_name, status_text="Preparing..."):
        """Add/update a per-mod sidebar row. Returns the status QLabel."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        name_label = QLabel(mod_name)
        name_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        status_label = QLabel(status_text)
        color = _MOD_STATUS_COLORS.get(status_text, "#b0b0b0")
        status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        row_layout.addWidget(name_label)
        row_layout.addWidget(status_label)
        # Insert before the trailing stretch
        insert_at = self._sidebar_layout.count() - 1
        self._sidebar_layout.insertWidget(insert_at, row_widget)
        self._sidebar_labels[mod_name] = status_label
        return status_label

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
    # URL / search handlers
    # ------------------------------------------------------------------

    def _on_url_changed(self, text):
        self._search_timer.stop()
        stripped = text.strip()
        if not stripped:
            self.search_results_list.setVisible(False)
            self.info_panel.setVisible(False)
            return
        # Skip live search when the field already contains a URL
        if stripped.startswith("http") or "mods.factorio.com" in stripped:
            return
        self._search_timer.start()

    def _perform_search(self):
        """Run after 500 ms debounce: fetch mod info in background."""
        query = self.url_edit.text().strip()
        if not query:
            return
        # Show placeholder immediately so the user knows something is happening
        self.search_results_list.clear()
        placeholder = QListWidgetItem("Searching\u2026")
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        self.search_results_list.addItem(placeholder)
        self.search_results_list.setVisible(True)

        worker = SearchWorker(query, parent=self)
        self._search_worker = worker
        worker.result.connect(self._on_search_result)
        worker.error.connect(lambda _e: self.search_results_list.setVisible(False))
        worker.start()

    @Slot(list)
    def _on_search_result(self, results: list):
        self.search_results_list.clear()
        if not results:
            self.search_results_list.setVisible(False)
            self._search_worker = None
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
        self.search_results_list.setVisible(True)
        self._search_worker = None

    def _on_result_selected(self, item: QListWidgetItem):
        mod_name = item.data(Qt.ItemDataRole.UserRole)
        # Block textChanged so the debounce timer doesn't re-trigger search
        self.url_edit.blockSignals(True)
        self.url_edit.setText(f"https://mods.factorio.com/mod/{mod_name}")
        self.url_edit.blockSignals(False)
        self.search_results_list.setVisible(False)
        # Automatically load the mod info panel
        self._on_load_mod()

    def _on_load_mod(self):
        url = self.url_edit.text().strip()
        if not url:
            self._notify("Please enter a mod URL or name.", "error")
            return
        self.search_results_list.setVisible(False)
        self.info_panel.setVisible(False)
        self.load_btn.setEnabled(False)
        worker = ResolveWorker(url, parent=self)
        self._resolve_worker = worker
        worker.resolved.connect(self._on_resolved)
        worker.error.connect(self._on_resolve_error)
        worker.finished.connect(lambda: self.load_btn.setEnabled(True))
        worker.start()

    @Slot(object)
    def _on_resolved(self, info):
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
                lbl.setText(f"<b>{prefix}</b>  {', '.join(items)}")
                lbl.setVisible(True)
            else:
                lbl.setVisible(False)

        any_deps = bool(req or opt or base or incompat)
        self.deps_hdr.setVisible(any_deps)
        self._dep_divider.setVisible(any_deps)

        self.info_panel.setVisible(True)
        self._resolve_worker = None

    @Slot(str)
    def _on_resolve_error(self, err):
        self._notify(f"Could not resolve mod: {err}", "error")

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

        # Reset UI
        self.search_results_list.setVisible(False)
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._sidebar_scroll.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setProperty("completed", "false")
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)
        self.console.clear()
        self._clear_sidebar()

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
            if self.status_manager:
                self.status_manager.push_status(
                    f"Downloading: {completed}/{total} mods ({pct}%)", "info"
                )

    @Slot(str, str)
    def _on_mod_status(self, mod_name, status_text):
        if mod_name in self._sidebar_labels:
            label = self._sidebar_labels[mod_name]
            label.setText(status_text)
            color = _MOD_STATUS_COLORS.get(status_text, "#b0b0b0")
            label.setStyleSheet(f"color: {color}; font-size: 11px;")
        else:
            self._add_sidebar_row(mod_name, status_text)

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
