"""Main application window — Qt implementation."""
from __future__ import annotations

import logging
from queue import Queue
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .status_manager import StatusManager
from .settings_page import SettingsPage
from .search_bar import GlobalSearchBar
from .mod_details_dialog import ModDetailsDialog
from .styles import load_and_apply_theme


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(
        self,
        log_queue: Optional[Queue] = None,
        log_bridge: Optional[object] = None,
    ) -> None:
        super().__init__()
        self.log_queue = log_queue
        self.log_bridge = log_bridge
        self.logger = logging.getLogger("factorio_mod_manager")

        self.setWindowTitle("🏭 Factorio Mod Manager v1.1.0")
        self.setMinimumSize(1100, 750)

        # Central widget + root layout
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header
        self._create_header(root_layout)

        # Body: left rail + page host
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left navigation rail
        self._nav_rail = self._create_nav_rail()
        body_layout.addWidget(self._nav_rail)

        # Page host
        self.page_host = QStackedWidget()
        self.page_host.setObjectName("pageHost")
        body_layout.addWidget(self.page_host, stretch=1)

        root_layout.addLayout(body_layout, stretch=1)

        # Status bar — height fixed per UI-SPEC.md
        self.statusBar().setFixedHeight(28)
        self.status_manager = StatusManager(self.statusBar())

        # Notification manager (created after central widget exists)
        self._create_notification_manager()

        # Phase 4: shared queue controller + drawer
        self._create_queue_infrastructure()

        # Global F5 refresh shortcut
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._on_refresh_requested)

        # Pages
        self._create_pages()

        # Launch maximized (D-13)
        self.showMaximized()

        # System theme auto-switch on OS palette change
        from PySide6.QtWidgets import QApplication as _QApp
        _app = _QApp.instance()
        if _app is not None:
            _app.paletteChanged.connect(self._on_palette_changed)

    def _create_header(self, root_layout: QVBoxLayout) -> None:
        """Create app header with title, subtitle, and accent separator."""
        header_widget = QWidget()
        header_widget.setObjectName("headerWidget")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 8, 16, 0)
        header_layout.setSpacing(2)

        # Title + subtitle row
        title_row = QHBoxLayout()
        title_row.setSpacing(0)

        title_label = QLabel("🏭 Factorio Mod Manager v1.1.0")
        # Inline style removed — now in dark_theme.qss#headerTitle
        title_label.setObjectName("headerTitle")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))

        subtitle_label = QLabel("Manage your Factorio mods")
        # Inline style removed — now in dark_theme.qss#headerSubtitle
        subtitle_label.setObjectName("headerSubtitle")
        subtitle_label.setFont(QFont("Segoe UI", 9))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title_row.addWidget(title_label)
        title_row.addStretch()
        # Utility zone: global search bar + settings shortcut button
        self._global_search_bar = GlobalSearchBar(self, parent=header_widget)
        title_row.addWidget(self._global_search_bar)

        # Phase 4: persistent queue badge between search and settings
        self._queue_badge = QPushButton("0")
        self._queue_badge.setObjectName("queueBadge")
        self._queue_badge.setFixedSize(32, 32)
        self._queue_badge.setToolTip("Operation queue (0 active)")
        self._queue_badge.setAccessibleName("Queue badge")
        self._queue_badge.setAccessibleDescription(
            "Shows number of active queue operations. Click to open the queue drawer."
        )
        self._queue_badge.clicked.connect(self.open_queue_drawer)
        title_row.addWidget(self._queue_badge)

        refresh_btn = QPushButton("\u21bb")
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setToolTip("Refresh current tab (F5)")
        refresh_btn.clicked.connect(self._on_refresh_requested)
        title_row.addWidget(refresh_btn)

        settings_btn = QPushButton("\u2699")
        settings_btn.setObjectName("settingsButton")
        settings_btn.setFixedSize(32, 32)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(lambda: self._navigate_to_page(3))
        title_row.addWidget(settings_btn)
        header_layout.addLayout(title_row)

        # Separator — QFrame#headerSeparator (QSS applies 1px accent color)
        separator = QFrame()
        separator.setObjectName("headerSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        header_layout.addWidget(separator)

        root_layout.addWidget(header_widget)

    def _create_nav_rail(self) -> QFrame:
        """Create the Fluent left navigation rail with three destination buttons."""
        from .styles.tokens import NAV_RAIL_WIDTH

        rail = QFrame()
        rail.setObjectName("navRail")
        rail.setFixedWidth(NAV_RAIL_WIDTH)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        nav_items = [
            ("⬇  Downloader", 0),
            ("✓  Checker & Updates", 1),
            ("📋  Logs", 2),
            ("\u2699  Settings", 3),
        ]

        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.toggled.connect(
                lambda checked, i=idx: self._on_nav_changed(i) if checked else None
            )
            self._nav_group.addButton(btn, idx)
            layout.addWidget(btn)

        layout.addStretch()
        return rail

    def _create_notification_manager(self) -> None:
        """Create notification manager anchored to central widget."""
        try:
            from .widgets import NotificationManager
            self.notification_manager = NotificationManager(self.centralWidget())
        except ImportError:
            self.notification_manager = None

    def _create_queue_infrastructure(self) -> None:
        """Instantiate the shared queue controller and drawer (Phase 4)."""
        from .queue_controller import QueueController
        from .queue_drawer import QueueDrawer

        self.queue_controller = QueueController(parent=self)
        self._queue_drawer = QueueDrawer(
            controller=self.queue_controller,
            parent=self.centralWidget(),
        )
        self._queue_drawer.raise_()

        # Badge update on every queue change
        self.queue_controller.badge_count_changed.connect(self._on_queue_badge_changed)
        self.queue_controller.drawer_open_requested.connect(self.open_queue_drawer)

    def open_queue_drawer(self) -> None:
        """Open the global queue drawer without navigating away from the current page."""
        if hasattr(self, '_queue_drawer'):
            self._queue_drawer.open_drawer()
            self._queue_drawer.raise_()

    def _on_queue_badge_changed(self, count: int, has_failed: bool) -> None:
        """Update header queue badge label and style."""
        if not hasattr(self, '_queue_badge'):
            return
        self._queue_badge.setText(str(count) if count > 0 else "0")
        self._queue_badge.setProperty("active", "true" if (count > 0 or has_failed) else "false")
        if has_failed:
            self._queue_badge.setToolTip(f"Operation queue — {count} active, failed items need attention")
        elif count > 0:
            self._queue_badge.setToolTip(f"Operation queue ({count} active)")
        else:
            self._queue_badge.setToolTip("Operation queue (idle)")
        # Force QSS dynamic property re-evaluation
        self._queue_badge.style().unpolish(self._queue_badge)
        self._queue_badge.style().polish(self._queue_badge)

    def _create_pages(self) -> None:
        """Create and add the three page widgets to the page host."""
        # Downloader page
        try:
            from .downloader_tab import DownloaderTab
            self.downloader_tab = DownloaderTab(status_manager=self.status_manager)
            if self.notification_manager:
                self.downloader_tab.set_notification_manager(self.notification_manager)
            if hasattr(self, "queue_controller"):
                self.downloader_tab.set_queue_controller(self.queue_controller)
            if self.log_bridge:
                self.downloader_tab.set_log_bridge(self.log_bridge)
            self.page_host.addWidget(self.downloader_tab)  # index 0
        except ImportError:
            placeholder = QWidget()
            QVBoxLayout(placeholder).addWidget(QLabel("Downloader (not yet implemented)"))
            self.page_host.addWidget(placeholder)

        # Checker page
        try:
            from .checker_tab import CheckerTab
            self.checker_tab = CheckerTab(
                logger=self.logger,
                status_manager=self.status_manager,
            )
            if self.notification_manager:
                self.checker_tab.set_notification_manager(self.notification_manager)
            if hasattr(self, "queue_controller"):
                self.checker_tab.set_queue_controller(self.queue_controller)
            self.page_host.addWidget(self.checker_tab)  # index 1
        except ImportError:
            placeholder = QWidget()
            QVBoxLayout(placeholder).addWidget(QLabel("Checker (not yet implemented)"))
            self.page_host.addWidget(placeholder)

        # Logger page
        try:
            from .logger_tab import LoggerTab
            self.logger_tab = LoggerTab(
                log_queue=self.log_queue if hasattr(self, 'log_queue') else None,
                log_bridge=self.log_bridge,
            )
            self.page_host.addWidget(self.logger_tab)  # index 2
        except ImportError:
            # Placeholder so index 2 always exists
            placeholder = QWidget()
            QVBoxLayout(placeholder).addWidget(QLabel("Logs (not yet implemented)"))
            self.page_host.addWidget(placeholder)

        # Settings page (index 3)
        self._settings_page = SettingsPage(self)
        self._settings_page.settings_saved.connect(self._on_settings_saved)
        self._settings_page.cancel_requested.connect(self._on_settings_cancel)
        self.page_host.addWidget(self._settings_page)  # index 3
        self._prev_page_idx: int = 0

        # Cross-widget signal connections
        if hasattr(self, "checker_tab") and hasattr(self, "_global_search_bar"):
            self.checker_tab.mods_loaded.connect(self._global_search_bar.set_installed_mods)
        if hasattr(self, "_global_search_bar"):
            self._global_search_bar.result_selected.connect(self._on_search_result_selected)

        # Activate first nav item and show first page
        first_btn = self._nav_group.button(0)
        if first_btn:
            first_btn.setChecked(True)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _on_nav_changed(self, index: int) -> None:
        """Central navigation handler; guards against leaving Settings with unsaved changes."""
        current = self.page_host.currentIndex()
        if current == 3 and index != 3 and self._settings_page.has_unsaved_changes():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved settings changes. Save before leaving?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._settings_page._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                # Restore Settings button without re-triggering guard
                settings_btn = self._nav_group.button(3)
                if settings_btn:
                    settings_btn.blockSignals(True)
                    settings_btn.setChecked(True)
                    settings_btn.blockSignals(False)
                return
            # Discard: fall through
        self._prev_page_idx = current
        if index == 3 and current != 3:
            self._settings_page.load_values()
        self.page_host.setCurrentIndex(index)

    def _navigate_to_page(self, index: int) -> None:
        """Navigate to page by checking the correct nav button."""
        btn = self._nav_group.button(index)
        if btn:
            btn.setChecked(True)
        else:
            self._on_nav_changed(index)

    def _on_refresh_requested(self) -> None:
        """Dispatch a refresh to the currently visible tab."""
        idx = self.page_host.currentIndex()
        tabs = [
            getattr(self, "downloader_tab", None),
            getattr(self, "checker_tab", None),
            getattr(self, "logger_tab", None),
            self._settings_page,
        ]
        tab = tabs[idx] if 0 <= idx < len(tabs) else None
        if tab is not None and hasattr(tab, "refresh"):
            tab.refresh()

    # ------------------------------------------------------------------
    # Settings page slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_settings_saved(self) -> None:
        """Refresh theme after SettingsPage.save() writes to config."""
        from ..utils.config import config as _cfg
        load_and_apply_theme(_cfg.get("theme", "dark"))

    @Slot()
    def _on_settings_cancel(self) -> None:
        """Return to the previous page when user cancels Settings."""
        btn = self._nav_group.button(self._prev_page_idx)
        if btn:
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)
        self.page_host.setCurrentIndex(self._prev_page_idx)

    # ------------------------------------------------------------------
    # Search result slot
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _on_search_result_selected(self, mod_name: str, source: str) -> None:
        """Open ModDetailsDialog for a search result from the header bar."""
        mods = getattr(self, "checker_tab", None)
        mods_dict = getattr(mods, "_mods", {}) if mods else {}

        if source == "installed":
            data = mods_dict.get(mod_name)
            if data is None:
                return
        else:
            # Fetch full portal metadata for non-installed mods
            from ..core.portal import FactorioPortalAPI
            try:
                portal = FactorioPortalAPI()
                data = portal.get_mod(mod_name)
            except Exception:
                # Fall back to minimal data if portal fetch fails
                data = {"name": mod_name}

        dialog = ModDetailsDialog(data, source, parent=self, installed_mods=mods_dict)
        dialog.exec()

    # ------------------------------------------------------------------
    # System theme auto-switch
    # ------------------------------------------------------------------

    @Slot()
    def _on_palette_changed(self) -> None:
        """Re-apply theme when OS palette changes (system theme mode only)."""
        from ..utils.config import config as _cfg
        if _cfg.get("theme", "dark") == "system":
            load_and_apply_theme("system")

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Reposition notification toasts when window resizes."""
        super().resizeEvent(event)
        if hasattr(self, "notification_manager") and self.notification_manager is not None:
            self.notification_manager.reposition_all()
