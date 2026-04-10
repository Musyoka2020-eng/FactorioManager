"""Main application window — Qt implementation."""
from __future__ import annotations

import logging
from queue import Queue
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .status_manager import StatusManager


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

        # Tab widget
        self.tab_widget = QTabWidget()
        root_layout.addWidget(self.tab_widget)

        # Status bar — height fixed per UI-SPEC.md
        self.statusBar().setFixedHeight(28)
        self.status_manager = StatusManager(self.statusBar())

        # Notification manager (created after central widget exists)
        self._create_notification_manager()

        # Tabs
        self._create_tabs()

        # Launch maximized (D-13)
        self.showMaximized()

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
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #e0e0e0;")

        subtitle_label = QLabel("Manage your Factorio mods")
        subtitle_label.setFont(QFont("Segoe UI", 9))
        subtitle_label.setStyleSheet("color: #b0b0b0;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(subtitle_label)
        header_layout.addLayout(title_row)

        # Separator — QFrame#headerSeparator (QSS applies 1px accent color)
        separator = QFrame()
        separator.setObjectName("headerSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        header_layout.addWidget(separator)

        root_layout.addWidget(header_widget)

    def _create_notification_manager(self) -> None:
        """Create notification manager anchored to central widget."""
        try:
            from .widgets import NotificationManager
            self.notification_manager = NotificationManager(self.centralWidget())
        except ImportError:
            self.notification_manager = None

    def _create_tabs(self) -> None:
        """Create and add the three tab widgets."""
        # Downloader tab
        try:
            from .downloader_tab import DownloaderTab
            self.downloader_tab = DownloaderTab(status_manager=self.status_manager)
            if self.notification_manager:
                self.downloader_tab.set_notification_manager(self.notification_manager)
            self.tab_widget.addTab(self.downloader_tab, "⬇️ Downloader")
        except ImportError:
            placeholder = QWidget()
            QVBoxLayout(placeholder).addWidget(QLabel("Downloader (not yet implemented)"))
            self.tab_widget.addTab(placeholder, "⬇️ Downloader")

        # Checker tab
        try:
            from .checker_tab import CheckerTab
            self.checker_tab = CheckerTab(
                logger=self.logger,
                status_manager=self.status_manager,
            )
            if self.notification_manager:
                self.checker_tab.set_notification_manager(self.notification_manager)
            self.tab_widget.addTab(self.checker_tab, "✓ Checker & Updates")
        except ImportError:
            placeholder = QWidget()
            QVBoxLayout(placeholder).addWidget(QLabel("Checker (not yet implemented)"))
            self.tab_widget.addTab(placeholder, "✓ Checker & Updates")

        # Logger tab (only if log_queue provided — same parity as Tkinter version)
        if self.log_queue is not None:
            try:
                from .logger_tab import LoggerTab
                self.logger_tab = LoggerTab(
                    log_queue=self.log_queue,
                    log_bridge=self.log_bridge,
                )
                self.tab_widget.addTab(self.logger_tab, "📋 Logs")
            except ImportError:
                placeholder = QWidget()
                QVBoxLayout(placeholder).addWidget(QLabel("Logs (not yet implemented)"))
                self.tab_widget.addTab(placeholder, "📋 Logs")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Reposition notification toasts when window resizes."""
        super().resizeEvent(event)
        if hasattr(self, "notification_manager") and self.notification_manager is not None:
            self.notification_manager.reposition_all()

