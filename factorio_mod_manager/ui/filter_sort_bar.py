"""Shared filter/sort bar and category chip bar — Phase 3."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QWidget,
)


class FilterSortBar(QWidget):
    """Horizontal filter/sort control bar.

    Emits filter_changed(query, status, sort_by, priority) with 200 ms debounce.
    status values: "all" | "up_to_date" | "outdated" | "selected"
    sort_by values: "name" | "version" | "downloads" | "date"
    priority: context-specific string injected by host page, or "" if no priority combo.
    """

    filter_changed = Signal(str, str, str, str)
    guidance_changed = Signal(str)   # "any" | "safe" | "review" | "risky"

    _STATUS_OPTIONS: list[tuple[str, str]] = [
        ("All", "all"),
        ("Up to date", "up_to_date"),
        ("Outdated", "outdated"),
        ("Selected", "selected"),
    ]
    _SORT_OPTIONS: list[tuple[str, str]] = [
        ("Name", "name"),
        ("Version", "version"),
        ("Downloads", "downloads"),
        ("Date", "date"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._priority_combo: QComboBox | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._emit_changed)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter mods\u2026")
        self._search_edit.setMinimumWidth(200)
        self._search_edit.textChanged.connect(self._schedule_emit)
        layout.addWidget(self._search_edit, stretch=1)

        self._status_combo = QComboBox()
        for label, _ in self._STATUS_OPTIONS:
            self._status_combo.addItem(label)
        self._status_combo.currentIndexChanged.connect(self._schedule_emit)
        layout.addWidget(self._status_combo)

        self._sort_combo = QComboBox()
        for label, _ in self._SORT_OPTIONS:
            self._sort_combo.addItem(label)
        self._sort_combo.currentIndexChanged.connect(self._schedule_emit)
        layout.addWidget(self._sort_combo)

    def add_priority_combo(self, options: list[str]) -> None:
        """Inject a context-specific priority combo into this bar."""
        self._priority_combo = QComboBox()
        for label in options:
            self._priority_combo.addItem(label)
        self._priority_combo.currentIndexChanged.connect(self._schedule_emit)
        self.layout().addWidget(self._priority_combo)

    _GUIDANCE_OPTIONS: list[tuple[str, str]] = [
        ("Any guidance", "any"),
        ("Safe", "safe"),
        ("Review", "review"),
        ("Risky", "risky"),
    ]

    def add_guidance_combo(self) -> None:
        """Inject the guidance tier filter combo. Call once from CheckerTab._setup_ui."""
        self._guidance_combo = QComboBox()
        for label, _ in self._GUIDANCE_OPTIONS:
            self._guidance_combo.addItem(label)
        self._guidance_combo.currentIndexChanged.connect(self._on_guidance_changed)
        self.layout().addWidget(self._guidance_combo)

    def _on_guidance_changed(self) -> None:
        if not hasattr(self, "_guidance_combo"):
            return
        value = self._GUIDANCE_OPTIONS[self._guidance_combo.currentIndex()][1]
        self.guidance_changed.emit(value)

    def _schedule_emit(self) -> None:
        self._debounce.start()

    def _emit_changed(self) -> None:
        query = self._search_edit.text().strip()
        status = self._STATUS_OPTIONS[self._status_combo.currentIndex()][1]
        sort_by = self._SORT_OPTIONS[self._sort_combo.currentIndex()][1]
        priority = (
            self._priority_combo.currentText().lower()
            if self._priority_combo is not None
            else ""
        )
        self.filter_changed.emit(query, status, sort_by, priority)

    def get_query(self) -> str:
        """Return current search text (for external callers)."""
        return self._search_edit.text().strip()


class CategoryChipsBar(QWidget):
    """Horizontal scrollable category chip selector for portal browse.

    Emits category_selected(category: str). Empty string means "All".
    Uses hardcoded KNOWN_CATEGORIES as initial chip set.
    Dynamic QSS property [selected="true"] drives accent chip highlight.
    """

    category_selected = Signal(str)

    # Each entry is (display_label, api_value).  "All" chip uses the sentinel
    # value "All" and emits "" (empty string) to mean "no filter".
    KNOWN_CATEGORIES: list[tuple[str, str]] = [
        ("All",           "All"),
        ("Content",       "content"),
        ("Overhaul",      "overhaul"),
        ("Tweaks",        "tweaks"),
        ("Utilities",     "utilities"),
        ("Scenarios",     "scenarios"),
        ("Mod Packs",     "mod-packs"),
        ("Localizations", "localizations"),
        ("Internal",      "internal"),
        ("No category",   "__no_category__"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_chip: QPushButton | None = None
        self._setup_ui()
        self.load_categories(self.KNOWN_CATEGORIES)

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(36)

        self._chips_widget = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(8, 4, 8, 4)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._scroll.setWidget(self._chips_widget)
        outer.addWidget(self._scroll)

    def load_categories(self, categories: list) -> None:
        """Replace current chips with a new category list.

        *categories* may be ``list[str]`` (label == value) or
        ``list[tuple[str, str]]`` (display_label, api_value).
        """
        # Remove all widgets except trailing stretch
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._active_chip = None

        for entry in categories:
            if isinstance(entry, tuple):
                label, value = entry
            else:
                label = value = entry
            btn = QPushButton(label)
            btn.setObjectName("categoryChip")
            btn.setProperty("category_value", value)
            btn.clicked.connect(
                lambda checked=False, v=value, b=btn: self._on_chip_clicked(v, b)
            )
            # Insert before trailing stretch
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, btn)

        # Activate "All" chip by default
        first = self._chips_layout.itemAt(0).widget() if self._chips_layout.count() > 1 else None
        if first:
            self._set_active(first)

    def _on_chip_clicked(self, value: str, btn: QPushButton) -> None:
        self._set_active(btn)
        # "All" sentinel → emit empty string (no category filter)
        self.category_selected.emit("" if value == "All" else value)

    def _set_active(self, btn: QPushButton) -> None:
        if self._active_chip is not None:
            self._active_chip.setProperty("selected", False)
            self._active_chip.style().unpolish(self._active_chip)
            self._active_chip.style().polish(self._active_chip)
        btn.setProperty("selected", True)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        self._active_chip = btn

    def select_chip(self, value: str) -> None:
        """Programmatically activate the chip matching *value* without emitting the signal.

        *value* is the api_value (e.g. ``"content"``, ``"All"``).
        """
        for i in range(self._chips_layout.count()):
            widget = self._chips_layout.itemAt(i).widget()
            if not isinstance(widget, QPushButton):
                continue
            chip_val = widget.property("category_value")
            # Fall back to button text for chips created without the property
            if chip_val is None:
                chip_val = widget.text()
            if chip_val == value:
                self._set_active(widget)
                return


# ---------------------------------------------------------------------------
# VersionFilterBar — Factorio version chip selector
# ---------------------------------------------------------------------------

class VersionFilterBar(QWidget):
    """Horizontal chip bar for filtering mods by Factorio version.

    Emits version_selected(version: str).
    Empty string means "All Versions".
    """

    version_selected = Signal(str)

    KNOWN_VERSIONS: list[tuple[str, str]] = [
        ("All Versions",  ""),
        ("Space Age 2.0", "2.0"),
        ("Legacy 1.1",    "1.1"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_chip: QPushButton | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(34)

        self._chips_widget = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(8, 3, 8, 3)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._scroll.setWidget(self._chips_widget)
        outer.addWidget(self._scroll)

        for label, value in self.KNOWN_VERSIONS:
            btn = QPushButton(label)
            btn.setObjectName("categoryChip")
            btn.setProperty("category_value", value)
            btn.clicked.connect(
                lambda checked=False, v=value, b=btn: self._on_chip_clicked(v, b)
            )
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, btn)

        # Activate "All Versions" by default
        first = self._chips_layout.itemAt(0).widget() if self._chips_layout.count() > 1 else None
        if first:
            self._set_active(first)

    def _on_chip_clicked(self, value: str, btn: QPushButton) -> None:
        self._set_active(btn)
        self.version_selected.emit(value)

    def _set_active(self, btn: QPushButton) -> None:
        if self._active_chip is not None:
            self._active_chip.setProperty("selected", False)
            self._active_chip.style().unpolish(self._active_chip)
            self._active_chip.style().polish(self._active_chip)
        btn.setProperty("selected", True)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        self._active_chip = btn

