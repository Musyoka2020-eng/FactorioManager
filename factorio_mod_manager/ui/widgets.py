"""Custom UI widgets — Qt implementation."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPropertyAnimation, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Maximum active notifications (DoS mitigation — T-03-02)
_MAX_ACTIVE = 5

# Icon glyphs per notification type
_ICONS: dict[str, str] = {
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
    "info": "ℹ",
}

# Icon colors per type (matches tokens.py / UI-SPEC.md)
_ICON_COLORS: dict[str, str] = {
    "success": "#4ec952",
    "error": "#d13438",
    "warning": "#ffad00",
    "info": "#0078d4",
}


class Notification(QFrame):
    """Toast-style notification overlay widget with optional auto-dismiss fade.

    Parent must be ``centralWidget()`` (or another container widget).
    Position is managed externally by ``NotificationManager``.
    """

    dismissed = Signal()

    def __init__(
        self,
        container: QWidget,
        message: str,
        notification_type: str = "info",
        duration_ms: int = 4000,
        actions: Optional[list[tuple[str, Callable]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(container if parent is None else parent)
        self._container = container
        self._duration_ms = duration_ms
        self._actions = actions or []
        self._anim: Optional[QPropertyAnimation] = None  # held to prevent GC

        # Apply QSS dynamic property — style().unpolish/polish forces re-evaluation
        self.setProperty("notifType", notification_type)
        self.style().unpolish(self)
        self.style().polish(self)

        self.setFixedWidth(420)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self._build_ui(message, notification_type)
        self.adjustSize()

        # Schedule auto-dismiss
        if duration_ms > 0 and not self._actions:
            QTimer.singleShot(duration_ms, self._start_fade)

    def _build_ui(self, message: str, notification_type: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        # Main row: icon + message + close button
        main_row = QHBoxLayout()
        main_row.setSpacing(10)

        icon_label = QLabel(_ICONS.get(notification_type, "ℹ"))
        icon_label.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {_ICON_COLORS.get(notification_type, '#0078d4')}; background: transparent;"
        )
        icon_label.setFixedWidth(20)
        main_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #e0e0e0; background: transparent; font-size: 10pt;")
        main_row.addWidget(msg_label, 1)

        # Close (×) button — always shown
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton { color: #b0b0b0; background: transparent; border: none; font-size: 10pt; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        close_btn.clicked.connect(self._dismiss_immediate)
        main_row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(main_row)

        # Action buttons row (persistent toasts)
        if self._actions:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.addStretch()
            for label, callback in self._actions:
                btn = QPushButton(label)
                if label.lower() in ("delete", "remove", "confirm"):
                    btn.setObjectName("destructiveButton")
                btn.clicked.connect(lambda _checked=False, cb=callback: self._action_click(cb))
                btn_row.addWidget(btn)
            outer.addLayout(btn_row)

    def _action_click(self, callback: Callable) -> None:
        """Invoke action callback then dismiss."""
        try:
            callback()
        finally:
            self._dismiss_immediate()

    def _start_fade(self) -> None:
        """Begin 300ms opacity fade-out, then deleteLater."""
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._anim = QPropertyAnimation(effect, b"opacity", self)
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_fade_finished)
        self._anim.start()

    def _on_fade_finished(self) -> None:
        self.dismissed.emit()
        self.deleteLater()

    def _dismiss_immediate(self) -> None:
        """Skip fade; delete immediately."""
        if self._anim is not None:
            self._anim.stop()
        self.dismissed.emit()
        self.deleteLater()


class NotificationManager:
    """Positions and manages a stack of Notification toasts anchored top-right.

    Toasts are children of ``container`` (``centralWidget()``).
    Call ``reposition_all()`` from ``MainWindow.resizeEvent``.
    """

    def __init__(self, container: QWidget) -> None:
        self._container = container
        self._active: list[Notification] = []

    def show(
        self,
        message: str,
        notification_type: str = "info",
        duration_ms: int = 4000,
        actions: Optional[list[tuple[str, Callable]]] = None,
    ) -> Notification:
        """Create and display a toast notification."""
        # DoS mitigation (T-03-02): evict oldest auto-dismiss toast if at cap
        if len(self._active) >= _MAX_ACTIVE:
            oldest = next(
                (n for n in self._active if n._duration_ms > 0 and not n._actions),
                self._active[0],
            )
            oldest._dismiss_immediate()

        notif = Notification(
            container=self._container,
            message=message,
            notification_type=notification_type,
            duration_ms=duration_ms,
            actions=actions,
        )
        notif.dismissed.connect(lambda: self._on_dismissed(notif))
        self._active.append(notif)
        notif.show()
        notif.raise_()
        self.reposition_all()
        return notif

    def reposition_all(self) -> None:
        """Snap all active toasts to top-right of container, stacked vertically."""
        right_margin = 16
        top_start = 16
        gap = 8

        y = top_start
        for notif in list(self._active):
            if notif.isVisible():
                x = self._container.width() - notif.width() - right_margin
                notif.move(x, y)
                notif.raise_()
                y += notif.height() + gap

    def _on_dismissed(self, notif: Notification) -> None:
        """Remove dismissed toast from active list and restack."""
        if notif in self._active:
            self._active.remove(notif)
        self.reposition_all()
