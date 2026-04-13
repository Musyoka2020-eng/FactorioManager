"""Mod details popup dialog — Phase 5 (3-tab: Overview / Dependencies / Changelog)."""
from __future__ import annotations

from typing import Union

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import Mod, ModStatus
from ..core.dependency_graph import DepType, DepState, DepNode, build_dep_graph
from ..core.portal import FactorioPortalAPI


# ---------------------------------------------------------------------------
# Status display mapping (matches CheckerPresenter.STATUS_COLORS)
# ---------------------------------------------------------------------------

_STATUS_DISPLAY = {
    ModStatus.UP_TO_DATE: ("\u2713 Up to date", "#4ec952"),
    ModStatus.OUTDATED:   ("\u2b06 Outdated",   "#ffad00"),
    ModStatus.UNKNOWN:    ("? Unknown",          "#b0b0b0"),
    ModStatus.ERROR:      ("\u2717 Error",        "#d13438"),
}


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------


class DepGraphWorker(QThread):
    """Runs build_dep_graph() in a background thread."""

    graph_ready = Signal(list)   # list[DepNode]
    error = Signal(str)

    def __init__(
        self,
        mod_name: str,
        installed_mods: dict,
        full: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._mod_name = mod_name
        self._installed_mods = installed_mods
        self._full = full
        self._should_stop = False

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True

    def run(self) -> None:
        try:
            if self._should_stop:
                return
            portal = FactorioPortalAPI()
            nodes = build_dep_graph(
                self._mod_name, self._installed_mods, portal, full=self._full
            )
            if not self._should_stop:
                self.graph_ready.emit(nodes)
        except Exception as exc:
            if not self._should_stop:
                self.error.emit(str(exc))


class ChangelogWorker(QThread):
    """Fetches mod changelog in a background thread."""

    changelog_ready = Signal(dict)   # Dict[str, str] — empty dict on error
    error = Signal(str)

    def __init__(self, mod_name: str, parent=None):
        super().__init__(parent)
        self._mod_name = mod_name
        self._should_stop = False

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True

    def run(self) -> None:
        try:
            if self._should_stop:
                return
            portal = FactorioPortalAPI()
            data = portal.get_mod_changelog(self._mod_name)
            if not self._should_stop:
                self.changelog_ready.emit(data)
        except Exception as exc:
            if not self._should_stop:
                self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# DependenciesWidget
# ---------------------------------------------------------------------------


class DependenciesWidget(QWidget):
    """Dependency tree inspector with Simplified / Full mode toggle."""

    def __init__(
        self,
        mod_name: str,
        mod: "Mod | None",
        installed_mods: "dict | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mod_name = mod_name
        self._mod = mod
        self._installed_mods: dict = installed_mods or {}
        self._loaded = False
        self._full_mode = False
        self._worker: DepGraphWorker | None = None
        self._dep_graph_request_id: int = 0

        self._setup_ui()

    # ------------------------------------------------------------------ setup

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._loading_lbl = QLabel("Loading dependencies\u2026")
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._loading_lbl)

        self._error_lbl = QLabel(
            "We could not load dependency details. Check your connection, "
            "then reopen details or run Check for Updates again."
        )
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setVisible(False)
        root.addWidget(self._error_lbl)

        self._empty_lbl = QLabel("No dependency data available.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

        # Content widget (hidden until loaded)
        self._content_widget = QWidget()
        self._content_widget.setVisible(False)
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        self._simplified_btn = QPushButton("Simplified")
        self._simplified_btn.setCheckable(True)
        self._simplified_btn.setChecked(True)
        self._mode_group.addButton(self._simplified_btn, 0)

        self._full_btn = QPushButton("Full")
        self._full_btn.setCheckable(True)
        self._mode_group.addButton(self._full_btn, 1)

        toolbar_layout.addWidget(self._simplified_btn)
        toolbar_layout.addWidget(self._full_btn)

        # Legend chips
        for label_text, color in [
            ("\u2713 Installed", "#4ec952"),
            ("\u2717 Missing", "#d13438"),
            ("\u25cb Portal", "#b0b0b0"),
            ("\U0001f512 Expansion", "#b0b0b0"),
            ("\u21ba Circular", "#ffad00"),
        ]:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {color};")
            toolbar_layout.addWidget(lbl)

        toolbar_layout.addStretch()

        self._collapse_all_btn = QPushButton("\u229f Collapse All")
        self._collapse_all_btn.setVisible(False)
        self._collapse_all_btn.clicked.connect(lambda: self._tree.collapseAll())
        toolbar_layout.addWidget(self._collapse_all_btn)

        content_layout.addWidget(toolbar)

        # Splitter: tree (left) + inspector (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Dependency", "State", "Constraint"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setMinimumWidth(300)
        self._tree.currentItemChanged.connect(self._update_inspector)
        splitter.addWidget(self._tree)

        inspector_scroll = QScrollArea()
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setMinimumWidth(240)
        self._inspector_widget = QWidget()
        self._inspector_layout = QVBoxLayout(self._inspector_widget)
        self._inspector_layout.setContentsMargins(8, 8, 8, 8)
        self._inspector_layout.setSpacing(4)
        self._inspector_layout.addStretch()
        inspector_scroll.setWidget(self._inspector_widget)
        splitter.addWidget(inspector_scroll)

        splitter.setSizes([500, 240])
        content_layout.addWidget(splitter, stretch=1)

        root.addWidget(self._content_widget, stretch=1)

        self._simplified_btn.clicked.connect(self._on_mode_simplified)
        self._full_btn.clicked.connect(self._on_mode_full)

    # ------------------------------------------------------------------ mode

    def _stop_worker(self) -> None:
        """Stop the background worker thread if running."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait(1000)  # Wait up to 1 second

    def _on_mode_simplified(self) -> None:
        self._full_mode = False
        self._collapse_all_btn.setVisible(False)
        if self._loaded:
            self._loaded = False
            self.ensure_loaded()

    def _on_mode_full(self) -> None:
        self._full_mode = True
        self._collapse_all_btn.setVisible(True)
        if self._loaded:
            self._loaded = False
            self.ensure_loaded()

    # ------------------------------------------------------------------ lazy load

    def ensure_loaded(self) -> None:
        """Trigger lazy load. Safe to call multiple times."""
        if self._loaded:
            return
        self._loading_lbl.setVisible(True)
        self._content_widget.setVisible(False)
        self._error_lbl.setVisible(False)
        self._empty_lbl.setVisible(False)

        # Cancel any in-flight worker before starting a new one
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait()

        self._dep_graph_request_id += 1
        current_token = self._dep_graph_request_id

        self._worker = DepGraphWorker(
            self._mod_name, self._installed_mods, self._full_mode, parent=self
        )
        self._worker.graph_ready.connect(
            lambda nodes, _tok=current_token: self._on_graph_ready(nodes, _tok)
        )
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    @Slot(list)
    def _on_graph_ready(self, nodes: list, token: int = 0) -> None:
        # Discard results from a superseded request (stale worker)
        if token != self._dep_graph_request_id:
            return
        self._loaded = True
        if not nodes:
            self._empty_lbl.setVisible(True)
            self._loading_lbl.setVisible(False)
            return
        self._loading_lbl.setVisible(False)
        self._content_widget.setVisible(True)
        self._populate_tree(nodes)

    @Slot(str)
    def _on_load_error(self, _msg: str) -> None:
        self._error_lbl.setVisible(True)
        self._loading_lbl.setVisible(False)
        self._content_widget.setVisible(False)

    # ------------------------------------------------------------------ tree

    def _populate_tree(self, nodes: list) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()

        groups: dict[DepType, tuple[str, list]] = {
            DepType.REQUIRED:     ("Required", []),
            DepType.OPTIONAL:     ("Optional", []),
            DepType.INCOMPATIBLE: ("Conflicts", []),
            DepType.EXPANSION:    ("Expansion Requirements", []),
        }
        for node in nodes:
            groups[node.dep_type][1].append(node)

        _STATE_CHIP: dict[DepState, tuple[str, str]] = {
            DepState.INSTALLED:   ("\u2713 Installed",        "#4ec952"),
            DepState.MISSING:     ("\u2717 Missing",         "#d13438"),
            DepState.PORTAL_ONLY: ("\u25cb Portal",          "#b0b0b0"),
            DepState.EXPANSION:   ("\U0001f512 Non-downloadable", "#b0b0b0"),
            DepState.CIRCULAR:    ("\u21ba Circular",         "#ffad00"),
        }

        for dep_type, (group_label, dep_nodes) in groups.items():
            group_item = QTreeWidgetItem([group_label])
            f = group_item.font(0)
            f.setBold(True)
            group_item.setFont(0, f)
            self._tree.addTopLevelItem(group_item)

            if not dep_nodes:
                none_item = QTreeWidgetItem(["(none)", "", ""])
                none_item.setForeground(0, QColor("#b0b0b0"))
                fi = none_item.font(0)
                fi.setItalic(True)
                none_item.setFont(0, fi)
                group_item.addChild(none_item)
            else:
                for node in dep_nodes:
                    chip_text, chip_color = _STATE_CHIP.get(
                        node.state, ("", "#b0b0b0")
                    )
                    item = QTreeWidgetItem([
                        node.name,
                        chip_text,
                        node.version_constraint,
                    ])
                    item.setForeground(1, QColor(chip_color))
                    item.setData(0, Qt.ItemDataRole.UserRole, node)

                    if dep_type == DepType.OPTIONAL and not self._full_mode:
                        item.setForeground(0, QColor("#b0b0b0"))

                    group_item.addChild(item)

                    for child in node.children:
                        c_chip, c_color = _STATE_CHIP.get(child.state, ("", "#b0b0b0"))
                        child_item = QTreeWidgetItem([
                            f"  \u2514 {child.name}",
                            c_chip,
                            child.version_constraint,
                        ])
                        child_item.setForeground(1, QColor(c_color))
                        child_item.setData(0, Qt.ItemDataRole.UserRole, child)
                        item.addChild(child_item)

            group_item.setExpanded(True)

        self._tree.blockSignals(False)

    # ------------------------------------------------------------------ inspector

    def _update_inspector(
        self, current: "QTreeWidgetItem | None", _previous: "QTreeWidgetItem | None"
    ) -> None:
        while self._inspector_layout.count() > 1:
            item = self._inspector_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if current is None:
            return

        node: "DepNode | None" = current.data(0, Qt.ItemDataRole.UserRole)
        if node is None:
            return

        _STATE_COLOR: dict[DepState, str] = {
            DepState.INSTALLED:   "#4ec952",
            DepState.MISSING:     "#d13438",
            DepState.PORTAL_ONLY: "#b0b0b0",
            DepState.EXPANSION:   "#b0b0b0",
            DepState.CIRCULAR:    "#ffad00",
        }

        def _add_lbl(text: str, bold: bool = False, color: str = "") -> None:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            if bold:
                f = lbl.font()
                f.setBold(True)
                lbl.setFont(f)
            if color:
                lbl.setStyleSheet(f"color: {color};")
            self._inspector_layout.insertWidget(
                self._inspector_layout.count() - 1, lbl
            )

        _add_lbl(node.name, bold=True)
        _add_lbl(f"Type: {node.dep_type.value.title()}")
        color = _STATE_COLOR.get(node.state, "")
        _add_lbl(f"State: {node.state.value.replace('_', ' ').title()}", color=color)

        if node.installed_version:
            _add_lbl(f"Installed: v{node.installed_version}")
        if node.version_constraint:
            _add_lbl(f"Requires: {node.version_constraint}")

        if node.state == DepState.EXPANSION:
            _add_lbl(
                "Requires official Factorio content. This requirement is informational "
                "and cannot be queued as a mod download.",
                color="#b0b0b0",
            )
        elif node.state == DepState.MISSING:
            _add_lbl(
                "This mod is required but not installed. "
                "Consider downloading it before updating.",
                color="#d13438",
            )
        elif node.state == DepState.CIRCULAR:
            _add_lbl(
                "Circular dependency detected — this node was already visited "
                "in the current tree path.",
                color="#ffad00",
            )


# ---------------------------------------------------------------------------
# ChangelogWidget
# ---------------------------------------------------------------------------


class ChangelogWidget(QWidget):
    """Version-delta changelog scroll view."""

    def __init__(
        self,
        mod_name: str,
        installed_version: "str | None",
        latest_version: "str | None",
        parent=None,
    ):
        super().__init__(parent)
        self._mod_name = mod_name
        self._installed_version = installed_version
        self._latest_version = latest_version
        self._loaded = False
        self._worker: ChangelogWorker | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        self._loading_lbl = QLabel("Loading changelog\u2026")
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._loading_lbl)

        self._empty_lbl = QLabel(
            "This mod does not expose changelog entries for the selected release path."
        )
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVisible(False)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        self._delta_header_lbl = QLabel()
        self._delta_header_lbl.setVisible(False)
        f = self._delta_header_lbl.font()
        f.setBold(True)
        self._delta_header_lbl.setFont(f)
        self._content_layout.addWidget(self._delta_header_lbl)

        self._scroll_area.setWidget(self._content_widget)
        root.addWidget(self._scroll_area, stretch=1)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _sort_versions(versions: list) -> list:
        def _key(v: str):
            try:
                return tuple(int(x) for x in v.split(".") if x.isdigit())
            except Exception:
                return (0,)

        return sorted(versions, key=_key, reverse=True)

    @staticmethod
    def _is_newer(a: str, b: str) -> bool:
        def _tup(v: str):
            try:
                return tuple(int(x) for x in v.split(".") if x.isdigit())
            except Exception:
                return (0,)

        return _tup(a) > _tup(b)

    def _make_entry_widget(self, version: str, text: str, expanded: bool) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        hdr = QLabel(f"Version {version}")
        hdr.setTextFormat(Qt.TextFormat.PlainText)
        f = hdr.font()
        f.setBold(True)
        hdr.setFont(f)
        vbox.addWidget(hdr)

        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(text)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(9)
        te.setFont(fixed_font)
        te.document().setTextWidth(te.viewport().width() or 400)
        te.setFixedHeight(min(int(te.document().size().height()) + 12, 300))

        if not expanded:
            te.setVisible(False)
            toggle_lbl = QLabel("\u25b6 Show")
            toggle_lbl.setStyleSheet("color: #0078d4; cursor: pointer;")
            toggle_lbl.setCursor(Qt.CursorShape.PointingHandCursor)

            def _toggle(_e=None, _te=te, _lbl=toggle_lbl):
                _te.setVisible(not _te.isVisible())
                _lbl.setText("\u25bc Hide" if _te.isVisible() else "\u25b6 Show")

            toggle_lbl.mousePressEvent = _toggle
            vbox.addWidget(toggle_lbl)

        vbox.addWidget(te)
        return container

    # ------------------------------------------------------------------ public

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loading_lbl.setVisible(True)
        self._scroll_area.setVisible(False)
        self._empty_lbl.setVisible(False)

        self._worker = ChangelogWorker(self._mod_name, parent=self)
        self._worker.changelog_ready.connect(self._on_changelog_ready)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    @Slot(dict)
    def _on_changelog_ready(self, data: dict) -> None:
        self._loaded = True
        self._loading_lbl.setVisible(False)
        if not data:
            self._empty_lbl.setVisible(True)
            return

        sorted_versions = self._sort_versions(list(data.keys()))

        if self._installed_version:
            delta_versions = [
                v for v in sorted_versions
                if self._is_newer(v, self._installed_version)
            ]
            history_versions = [
                v for v in sorted_versions
                if not self._is_newer(v, self._installed_version)
            ]
        else:
            delta_versions = sorted_versions[:1]
            history_versions = sorted_versions[1:]

        if delta_versions and self._installed_version:
            n = len(delta_versions)
            label = self._latest_version or sorted_versions[0]
            self._delta_header_lbl.setText(
                f"Changes since v{self._installed_version} \u2192 v{label}"
                f" ({n} entr{'y' if n == 1 else 'ies'})"
            )
            self._delta_header_lbl.setVisible(True)

        for version in delta_versions:
            widget = self._make_entry_widget(version, data[version], expanded=True)
            self._content_layout.addWidget(widget)

        if history_versions:
            hist_lbl = QLabel("Older history")
            hist_lbl.setTextFormat(Qt.TextFormat.PlainText)
            hist_lbl.setStyleSheet("color: #b0b0b0;")
            self._content_layout.addWidget(hist_lbl)
            for version in history_versions:
                widget = self._make_entry_widget(version, data[version], expanded=False)
                self._content_layout.addWidget(widget)

        self._content_layout.addStretch()
        self._scroll_area.setVisible(True)

    @Slot(str)
    def _on_load_error(self, _msg: str) -> None:
        self._loaded = False
        self._loading_lbl.setVisible(False)
        self._empty_lbl.setText(
            "We could not load changelog details. Check your connection, "
            "then reopen details or run Check for Updates again."
        )
        self._empty_lbl.setVisible(True)
        self._scroll_area.setVisible(False)

    def _stop_worker(self) -> None:
        """Stop the background worker thread if running."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait(1000)  # Wait up to 1 second


# ---------------------------------------------------------------------------
# ModDetailsDialog — 3-tab shell
# ---------------------------------------------------------------------------


class ModDetailsDialog(QDialog):
    """Modal dialog showing details for a mod (3 tabs: Overview / Dependencies / Changelog).

    Accepts either a Mod dataclass instance (for installed mods) or a
    portal result dict (for portal search results).

    Args:
        data:           Mod dataclass or portal dict
        source:         "installed" | "portal"
        parent:         parent widget
        initial_tab:    "overview" | "dependencies" | "changelog" (default "overview")
        installed_mods: dict[str, Mod] of currently installed mods (for dep graph)
    """

    def __init__(
        self,
        data: Union[Mod, dict],
        source: str,
        parent=None,
        *,
        initial_tab: str = "overview",
        installed_mods: "dict | None" = None,
    ):
        super().__init__(parent)
        self.setMinimumSize(860, 620)
        self.setModal(True)

        self._mod: "Mod | None" = data if isinstance(data, Mod) else None
        self._installed_mods: dict = installed_mods or {}

        if isinstance(data, Mod):
            self._name = data.name
            self._title = data.title or data.name
            self._author = data.author or ""
            self._version = data.version or ""
            self._installed_version: "str | None" = data.version or None
            self._description = data.description or ""
            self._downloads: "int | None" = data.downloads or None
            self._status: "ModStatus | None" = data.status
            self._latest_version: "str | None" = getattr(data, "latest_version", None)
        else:
            self._name = data.get("name", "")
            self._title = data.get("title") or self._name
            self._author = data.get("owner", "")
            releases = data.get("releases", [])
            self._version = releases[-1].get("version", "") if releases else ""
            _installed_mod = self._installed_mods.get(self._name)
            self._installed_version = _installed_mod.version if _installed_mod is not None else None
            self._description = data.get("summary", "") or data.get("description", "")
            downloads = data.get("downloads_count")
            self._downloads = int(downloads) if downloads else None
            self._status = None
            self._latest_version = None

        self._source = source
        self._initial_tab = initial_tab
        self.setWindowTitle(self._title)
        self._setup_ui()

        self.resize(980, 700)

        _tab_map = {"overview": 0, "dependencies": 1, "changelog": 2}
        _idx = _tab_map.get(initial_tab, 0)
        if _idx != 0:
            self._tab_widget.setCurrentIndex(_idx)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(8)

        title_lbl = QLabel(self._title)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        title_lbl.setWordWrap(True)
        root.addWidget(title_lbl)

        meta_parts: list[str] = []
        if self._author:
            meta_parts.append(f"by {self._author}")
        if self._version:
            meta_parts.append(f"v{self._version}")
        if self._downloads is not None:
            meta_parts.append(f"{self._downloads:,} downloads")
        if meta_parts:
            meta_lbl = QLabel("  \u00b7  ".join(meta_parts))
            meta_lbl.setObjectName("searchResultMeta")
            meta_lbl.setTextFormat(Qt.TextFormat.PlainText)
            root.addWidget(meta_lbl)

        if self._status is not None:
            status_text, color = _STATUS_DISPLAY.get(
                self._status, ("? Unknown", "#b0b0b0")
            )
            status_lbl = QLabel(status_text)
            status_lbl.setTextFormat(Qt.TextFormat.PlainText)
            status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            root.addWidget(status_lbl)

            if self._status == ModStatus.OUTDATED and self._latest_version:
                latest_lbl = QLabel(f"Latest: v{self._latest_version}")
                latest_lbl.setTextFormat(Qt.TextFormat.PlainText)
                root.addWidget(latest_lbl)

        # Tab widget
        self._tab_widget = QTabWidget()

        # Tab 0: Overview (existing description)
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(0, 8, 0, 0)
        overview_layout.setSpacing(0)
        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setPlainText(self._description or "No description available.")
        overview_layout.addWidget(desc_edit)
        self._tab_widget.addTab(overview_tab, "Overview")

        # Tab 1: Dependencies
        self._deps_widget = DependenciesWidget(
            mod_name=self._name,
            mod=self._mod,
            installed_mods=self._installed_mods,
            parent=self,
        )
        self._tab_widget.addTab(self._deps_widget, "Dependencies")

        # Tab 2: Changelog
        self._changelog_widget = ChangelogWidget(
            mod_name=self._name,
            installed_version=self._installed_version,
            latest_version=self._latest_version,
            parent=self,
        )
        self._tab_widget.addTab(self._changelog_widget, "Changelog")

        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tab_widget, stretch=1)

        # Footer
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(8)

        if self._source == "portal":
            cta_label = "View on Portal"
            cta_btn = QPushButton(cta_label)
            cta_btn.setObjectName("accentButton")
            cta_btn.clicked.connect(self._on_cta)
            footer_layout.addWidget(cta_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        root.addWidget(footer)

    def _on_tab_changed(self, idx: int) -> None:
        if idx == 1:
            self._deps_widget.ensure_loaded()
        elif idx == 2:
            self._changelog_widget.ensure_loaded()

    def closeEvent(self, event) -> None:
        """Stop any running background workers before the dialog is destroyed."""
        self._deps_widget._stop_worker()
        self._changelog_widget._stop_worker()
        super().closeEvent(event)

    def _on_cta(self) -> None:
        if self._source == "portal" and self._name:
            import webbrowser
            webbrowser.open(f"https://mods.factorio.com/mod/{self._name}")
        self.accept()