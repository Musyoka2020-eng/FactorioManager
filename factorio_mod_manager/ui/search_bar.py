"""Global search bar and results popup — Phase 3."""
from __future__ import annotations

import logging
from typing import Dict

from PySide6.QtCore import QPoint, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core import Mod
from ..core.portal import FactorioPortalAPI, PortalAPIError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker: PortalSearchWorker
# ---------------------------------------------------------------------------

class PortalSearchWorker(QThread):
    """QThread that searches the portal for mods matching a query string."""

    result = Signal(list)   # list of portal result dicts
    error = Signal(str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self) -> None:
        try:
            portal = FactorioPortalAPI()
            results, _, _ = portal.search_mods(self._query, limit=8)
            self.result.emit(results)
        except PortalAPIError as exc:
            self.error.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — worker thread must never raise; emit error to UI
            self.error.emit(f"Search failed: {exc}")


# ---------------------------------------------------------------------------
# _ResultRow — clickable row widget
# ---------------------------------------------------------------------------

class _ResultRow(QWidget):
    """Clickable result row widget emitting activated() signal."""

    activated = Signal()

    def __init__(self, mod_name: str, meta: str, source: str, parent=None):
        super().__init__(parent)
        self._source = source
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        name_lbl = QLabel(mod_name)
        name_lbl.setTextFormat(Qt.TextFormat.PlainText)
        meta_lbl = QLabel(meta)
        meta_lbl.setTextFormat(Qt.TextFormat.PlainText)
        meta_lbl.setObjectName("searchResultMeta")
        layout.addWidget(name_lbl, stretch=1)
        layout.addWidget(meta_lbl)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.activated.emit()

    def activate(self) -> None:
        self.activated.emit()

    def set_focused(self, focused: bool) -> None:
        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# SearchResultsPopup
# ---------------------------------------------------------------------------

class SearchResultsPopup(QFrame):
    """Transient popup listing grouped search results below GlobalSearchBar.

    Groups: Installed (from mod dict) then Portal (from portal search).
    Emits result_selected(mod_name, source) when user clicks a result.
    Dismissed by: focus-out, Escape key, or explicit close().
    """

    result_selected = Signal(str, str)   # mod_name, source ("installed"|"portal")

    _MAX_HEIGHT = 480
    _POPUP_WIDTH = 400

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFixedWidth(self._POPUP_WIDTH)
        self.setObjectName("searchResultsPopup")
        self._focused_row: int = -1
        self._rows: list[_ResultRow] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMaximumHeight(self._MAX_HEIGHT)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 4, 0, 4)
        self._content_layout.setSpacing(0)

        self._empty_label = QLabel("No results")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setObjectName("searchEmptyLabel")
        self._empty_label.setVisible(False)
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_results(
        self,
        query: str,
        installed_mods: Dict[str, Mod],
        portal_results: list[dict],
    ) -> None:
        """Populate popup with installed + portal results and show it."""
        self._focused_row = -1
        self._clear_rows()

        installed_matches = [
            (name, mod)
            for name, mod in installed_mods.items()
            if query.lower() in name.lower()
            or query.lower() in (mod.title or "").lower()
        ][:5]

        portal_matches = portal_results[:5]

        if not installed_matches and not portal_matches:
            self._empty_label.setText(f"No mods match '{query}'.")
            self._empty_label.setVisible(True)
        else:
            self._empty_label.setVisible(False)
            if installed_matches:
                self._add_section_header("Installed")
                for name, mod in installed_matches:
                    status_text = (
                        mod.status.value.replace("_", " ").title() if mod.status else ""
                    )
                    self._add_result_row(name, status_text, "installed")
            if portal_matches:
                self._add_section_header("Portal")
                for entry in portal_matches:
                    name = entry.get("name", "")
                    dl = entry.get("downloads_count", 0)
                    meta = f"{dl:,} downloads" if dl else ""
                    self._add_result_row(name, meta, "portal")

        self._content.adjustSize()
        self.adjustSize()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _add_section_header(self, title: str) -> None:
        lbl = QLabel(title)
        lbl.setObjectName("searchSectionHeader")
        lbl.setContentsMargins(12, 4, 12, 2)
        insert_at = self._content_layout.count() - 1  # before stretch
        self._content_layout.insertWidget(insert_at, lbl)

    def _add_result_row(self, mod_name: str, meta: str, source: str) -> None:
        row = _ResultRow(mod_name, meta, source)
        row.activated.connect(
            lambda n=mod_name, s=source: self._on_result_activated(n, s)
        )
        insert_at = self._content_layout.count() - 1  # before stretch
        self._content_layout.insertWidget(insert_at, row)
        self._rows.append(row)

    def _on_result_activated(self, mod_name: str, source: str) -> None:
        self.result_selected.emit(mod_name, source)
        self.close()

    def _clear_rows(self) -> None:
        self._rows.clear()
        # Remove all items between index 1 (after empty_label) and last (stretch)
        while self._content_layout.count() > 2:
            item = self._content_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_Down:
            self._move_focus(1)
        elif key == Qt.Key.Key_Up:
            self._move_focus(-1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if 0 <= self._focused_row < len(self._rows):
                self._rows[self._focused_row].activate()
        else:
            super().keyPressEvent(event)

    def _move_focus(self, delta: int) -> None:
        if not self._rows:
            return
        self._focused_row = max(0, min(len(self._rows) - 1, self._focused_row + delta))
        for i, row in enumerate(self._rows):
            row.set_focused(i == self._focused_row)


# ---------------------------------------------------------------------------
# GlobalSearchBar
# ---------------------------------------------------------------------------

class GlobalSearchBar(QWidget):
    """Header search bar with Ctrl+K shortcut and debounced popup results.

    Set installed mods via set_installed_mods(mods: Dict[str, Mod]).
    When result clicked, emits result_selected(mod_name, source).
    """

    result_selected = Signal(str, str)   # mod_name, source ("installed"|"portal")

    def __init__(self, main_window: QWidget, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._installed_mods: Dict[str, Mod] = {}
        self._portal_worker: PortalSearchWorker | None = None
        self._portal_results: list[dict] = []
        self._popup: SearchResultsPopup | None = None

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._on_debounce_fired)

        self._setup_ui()

        # Ctrl+K shortcut on main window
        shortcut = QShortcut(QKeySequence("Ctrl+K"), main_window)
        shortcut.activated.connect(self._bar_edit.setFocus)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._bar_edit = QLineEdit()
        self._bar_edit.setObjectName("globalSearchBar")
        self._bar_edit.setPlaceholderText("Search mods\u2026  Ctrl+K")
        self._bar_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._bar_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._bar_edit)

    def set_installed_mods(self, mods: Dict[str, Mod]) -> None:
        """Called by MainWindow when CheckerTab finishes a scan."""
        self._installed_mods = mods

    def _on_text_changed(self, text: str) -> None:
        self._debounce.start()

    def _on_debounce_fired(self) -> None:
        query = self._bar_edit.text().strip()
        if not query:
            if self._popup and self._popup.isVisible():
                self._popup.close()
            return
        # Cancel previous portal worker
        if self._portal_worker and self._portal_worker.isRunning():
            self._portal_worker.result.disconnect(self._on_portal_results)
            self._portal_worker.error.disconnect(self._on_portal_error)
            self._portal_worker.requestInterruption()
            self._portal_worker.quit()
        worker = PortalSearchWorker(query, parent=self)
        self._portal_worker = worker
        worker.result.connect(self._on_portal_results)
        worker.error.connect(self._on_portal_error)
        worker.start()
        # Show installed results immediately; portal comes async
        self._show_popup(query, portal_results=[])

    @Slot(list)
    def _on_portal_results(self, results: list) -> None:
        self._portal_results = results
        query = self._bar_edit.text().strip()
        if query and self._popup and self._popup.isVisible():
            self._show_popup(query, portal_results=results)
        self._portal_worker = None

    def _on_portal_error(self, error: str) -> None:
        logger.warning("Portal search error: %s", error)
        self._portal_worker = None

    def _show_popup(self, query: str, portal_results: list) -> None:
        if self._popup is None:
            self._popup = SearchResultsPopup(self._main_window)
            self._popup.result_selected.connect(self._on_result_selected)

        # Anchor popup below search bar
        pos = self._bar_edit.mapToGlobal(QPoint(0, self._bar_edit.height()))
        self._popup.move(pos)
        self._popup.show_results(query, self._installed_mods, portal_results)
        self._popup.show()

    def _on_result_selected(self, mod_name: str, source: str) -> None:
        self.result_selected.emit(mod_name, source)
        self._bar_edit.clear()