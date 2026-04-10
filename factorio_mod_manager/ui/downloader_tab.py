"""Downloader tab UI — Qt implementation."""
from __future__ import annotations

import html as html_lib
import logging
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

    resolved = Signal(dict)
    error = Signal(str)

    def __init__(self, mod_url, parent=None):
        super().__init__(parent)
        self._mod_url = mod_url

    def run(self):
        try:
            portal = FactorioPortalAPI()
            info = portal.get_mod_by_url(self._mod_url)
            self.resolved.emit(info)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: SearchWorker  (500 ms debounce on URL field)
# ---------------------------------------------------------------------------

class SearchWorker(QThread):
    """QThread that looks up a search query on the portal."""

    result = Signal(dict)
    error = Signal(str)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self):
        try:
            portal = FactorioPortalAPI()
            info = portal.get_mod_by_url(self._query)
            self.result.emit(info)
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
        self._active_worker = None       # prevents GC before signal delivery
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

        # Mod info label (shown after resolve)
        self.mod_info_label = QLabel("")
        self.mod_info_label.setWordWrap(True)
        self.mod_info_label.setStyleSheet("color: #b0b0b0; font-size: 12px;")
        root.addWidget(self.mod_info_label)

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
        left_col.addWidget(self.console, stretch=1)
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
        if text.strip():
            self._search_timer.start()

    def _perform_search(self):
        """Run after 500 ms debounce: fetch mod info in background."""
        query = self.url_edit.text().strip()
        if not query:
            return
        worker = SearchWorker(query, parent=self)
        self._active_worker = worker
        worker.result.connect(self._on_search_result)
        worker.error.connect(lambda _e: None)   # silent fail
        worker.start()

    def _on_search_result(self, info):
        title = info.get("title") or info.get("name", "")
        author = info.get("owner", "")
        if title:
            self.mod_info_label.setText(f"📦 {title}  by {author}")
        self._active_worker = None

    def _on_load_mod(self):
        url = self.url_edit.text().strip()
        if not url:
            self._notify("Please enter a mod URL or name.", "error")
            return
        self.load_btn.setEnabled(False)
        worker = ResolveWorker(url, parent=self)
        self._active_worker = worker
        worker.resolved.connect(self._on_resolved)
        worker.error.connect(self._on_resolve_error)
        worker.finished.connect(lambda: self.load_btn.setEnabled(True))
        worker.start()

    @Slot(dict)
    def _on_resolved(self, info):
        title = info.get("title") or info.get("name", "")
        author = info.get("owner", "")
        summary = info.get("summary", "")
        parts = [f"📦 {title}  by {author}"]
        if summary:
            parts.append(summary[:120])
        self.mod_info_label.setText("  |  ".join(parts))

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
        self.download_btn.setEnabled(False)
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
