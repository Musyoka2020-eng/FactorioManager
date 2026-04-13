"""Profile Editor Dialog — manage which mods are in a profile and toggle their enabled state.

Features
--------
* Checkbox per row: checked = mod active in profile, unchecked = mod in profile but disabled.
* Auto-resolve required dependencies when a mod is enabled (adds missing deps to the profile).
* Category tabs derived from installed mod metadata + "Not Downloaded" for missing mods.
* Search bar (300 ms debounce) to filter by mod name.
* Pagination: 50 mods per page with Prev / Next controls.
* Right-click "Remove from Profile" context menu.
* Download button for mods that are in the profile but not installed locally.

``ProfileEditorDialog.download_requested`` is emitted with a list of mod names
when the user confirms a download from within the editor.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.profiles import Profile, ProfileStore

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# Pure helper functions (testable without Qt)
# ---------------------------------------------------------------------------


def resolve_dep_additions(
    mod_name: str,
    desired_mods: Set[str],
    disabled_in_profile: Set[str],
    installed_mods: Dict[str, Any],
) -> Tuple[List[str], List[str], List[str]]:
    """Compute dep changes needed when *mod_name* is (re-)enabled in the editor.

    Performs a BFS over all transitive required dependencies so that indirect
    requirements (A→B→C) are discovered and handled, not just direct ones.

    Returns
    -------
    to_add : list[str]
        Required dep names not yet in *desired_mods* → should be added to profile.
    to_unblock : list[str]
        Required dep names already in *desired_mods* but in *disabled_in_profile*
        → should be removed from the disabled set (auto-unblocked).
    to_download : list[str]
        Required dep names that are in neither *desired_mods* nor *installed_mods*
        → need downloading before the profile can work.
    """
    to_add: List[str] = []
    to_unblock: List[str] = []
    to_download: List[str] = []

    # BFS to traverse all transitive dependencies
    visited: Set[str] = set()
    queue: List[str] = [mod_name]

    while queue:
        current_name = queue.pop(0)
        if current_name in visited or current_name == "base":
            continue
        visited.add(current_name)

        current_mod = installed_mods.get(current_name)
        if current_mod is None:
            continue

        raw_deps: List[str] = getattr(current_mod, "raw_data", {}).get("dependencies", [])
        for raw in raw_deps:
            raw = raw.strip()
            if not raw or raw[0] in ("?", "!", "("):
                continue
            dep_name = raw.split()[0]
            if not dep_name or dep_name == "base" or dep_name in visited:
                continue

            # Classify this dependency
            if dep_name not in desired_mods:
                if dep_name in installed_mods:
                    if dep_name not in to_add:
                        to_add.append(dep_name)
                    # Add to queue to discover its transitive deps
                    queue.append(dep_name)
                else:
                    if dep_name not in to_download:
                        to_download.append(dep_name)
            elif dep_name in disabled_in_profile:
                if dep_name not in to_unblock:
                    to_unblock.append(dep_name)
                # Add to queue to discover its transitive deps
                queue.append(dep_name)
            else:
                # Already in desired_mods and enabled — still traverse its deps
                queue.append(dep_name)

    return to_add, to_unblock, to_download


def filter_and_page(
    items: List[Dict[str, Any]],
    query: str,
    category: str,
    page: int,
    page_size: int = _PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], int]:
    """Filter and paginate *items*.

    Parameters
    ----------
    items:
        Full list of row dicts (keys: mod_name, title, version, category, is_installed).
    query:
        Case-insensitive substring to match against mod_name / title.
    category:
        "All", "Not Downloaded", or a portal category string.
    page:
        0-based page index.
    page_size:
        Items per page (default ``_PAGE_SIZE``).

    Returns
    -------
    page_items : list[dict]
        Items for the requested page.
    total_pages : int
        Total number of pages (≥ 1).
    """
    q = query.strip().lower()
    filtered = []
    for item in items:
        # Category filter
        if category == "Not Downloaded" and item.get("is_installed", True):
            continue
        if category not in ("All", "Not Downloaded") and item.get("category", "Other") != category:
            continue
        # Text search
        if q and q not in item.get("mod_name", "").lower() and q not in item.get("title", "").lower():
            continue
        filtered.append(item)

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * page_size
    return filtered[start : start + page_size], total_pages


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class ProfileEditorDialog(QDialog):
    """Edit which mods belong to a profile and their enabled/disabled state.

    Parameters
    ----------
    profile:
        The Profile to edit (modified in-place on Save).
    installed_mods:
        Map of mod_name -> Mod from CheckerTab's current scan results.
    profile_store:
        Used to persist the profile after edits.
    queue_controller:
        Shared queue controller (passed through for download job creation in caller).
        The dialog emits ``download_requested`` instead of creating jobs directly.
    parent:
        Parent widget.
    """

    # Emitted with list of mod names when user confirms a download from the editor.
    download_requested = Signal(list)

    def __init__(
        self,
        profile: Profile,
        installed_mods: Dict[str, Any],
        profile_store: ProfileStore,
        queue_controller: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._installed_mods = installed_mods
        self._profile_store = profile_store
        self._queue_controller = queue_controller  # not used directly; for future use

        # Working state (staged — not written until Save)
        self._staged_desired: List[str] = list(profile.desired_mods)
        self._staged_disabled: Set[str] = set(profile.disabled_in_profile)

        # Display state
        self._current_page: int = 0
        self._current_category: str = "All"
        self._search_query: str = ""
        self._all_items: List[Dict[str, Any]] = []
        self._total_pages: int = 1

        self.setObjectName("profileEditorDialog")
        self.setWindowTitle(f"Edit Profile — {profile.name}")
        self.setMinimumWidth(960)
        self.setMinimumHeight(700)
        self.setModal(True)

        self._build_ui()
        self._build_all_items()
        self._refresh_category_tabs()
        self._refresh_page()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # Title
        title_lbl = QLabel(f"<b>{self._profile.name}</b> — Mod List")
        title_lbl.setObjectName("editorTitle")
        root.addWidget(title_lbl)

        sub_lbl = QLabel(
            "Check / uncheck mods to enable or disable them within this profile. "
            "Disabled mods stay in the profile but won't be activated on apply."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setObjectName("editorSubtitle")
        root.addWidget(sub_lbl)

        # Search bar
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search mods…")
        self._search_edit.setObjectName("editorSearch")
        search_row.addWidget(self._search_edit)
        root.addLayout(search_row)

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search_commit)
        self._search_edit.textChanged.connect(lambda _: self._search_timer.start())

        # Category tab bar (horizontal buttons)
        self._cat_row = QHBoxLayout()
        self._cat_row.setSpacing(4)
        self._cat_buttons: Dict[str, QPushButton] = {}
        root.addLayout(self._cat_row)

        # Mod tree
        self._tree = QTreeWidget()
        self._tree.setObjectName("editorTree")
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(0)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        headers = ["", "Mod Name", "Version", "Status", ""]
        self._tree.setHeaderLabels(headers)
        self._tree.setColumnWidth(0, 30)   # checkbox
        self._tree.setColumnWidth(1, 280)  # name
        self._tree.setColumnWidth(2, 80)   # version
        self._tree.setColumnWidth(3, 110)  # status chip
        self._tree.setColumnWidth(4, 100)  # download btn or dep badge
        self._tree.itemChanged.connect(self._on_item_toggled)
        root.addWidget(self._tree, stretch=1)

        # Pagination row
        page_row = QHBoxLayout()
        page_row.setSpacing(8)
        page_row.addStretch()
        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.setFixedWidth(80)
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_btn = QPushButton("Next →")
        self._next_btn.setFixedWidth(80)
        self._next_btn.clicked.connect(self._on_next_page)
        page_row.addWidget(self._prev_btn)
        page_row.addWidget(self._page_label)
        page_row.addWidget(self._next_btn)
        page_row.addStretch()
        root.addLayout(page_row)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setObjectName("accentButton")
        self._save_btn.clicked.connect(self._on_save)
        footer.addWidget(cancel_btn)
        footer.addWidget(self._save_btn)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _build_all_items(self) -> None:
        """Build the full row list from staged desired mods."""
        self._all_items = []
        desired_set = set(self._staged_desired)
        for mod_name in sorted(self._staged_desired, key=str.lower):
            if mod_name == "base":
                continue
            mod = self._installed_mods.get(mod_name)
            is_installed = mod is not None
            category = (
                getattr(mod, "raw_data", {}).get("category", "Other")
                if mod else "Not Downloaded"
            )
            version = getattr(mod, "version", "") if mod else ""
            title = getattr(mod, "title", mod_name) if mod else mod_name
            self._all_items.append(
                {
                    "mod_name": mod_name,
                    "title": title,
                    "version": version,
                    "category": category if is_installed else "Not Downloaded",
                    "is_installed": is_installed,
                }
            )

    def _categories(self) -> List[str]:
        cats: Set[str] = set()
        has_missing = False
        for item in self._all_items:
            if not item["is_installed"]:
                has_missing = True
            else:
                cats.add(item["category"])
        result = ["All"] + sorted(cats)
        if has_missing:
            result.append("Not Downloaded")
        return result

    # ------------------------------------------------------------------
    # Category tab helpers
    # ------------------------------------------------------------------

    def _refresh_category_tabs(self) -> None:
        """Rebuild the category button row."""
        # Remove ALL items from the layout (buttons and spacers) to prevent accumulation
        while self._cat_row.count():
            item = self._cat_row.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
        self._cat_buttons.clear()

        for cat in self._categories():
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setObjectName("catTabButton")
            btn.setChecked(cat == self._current_category)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            cat_name = cat
            btn.clicked.connect(lambda _=False, c=cat_name: self._on_category_changed(c))
            self._cat_row.addWidget(btn)
            self._cat_buttons[cat] = btn

        self._cat_row.addStretch()

    def _on_category_changed(self, category: str) -> None:
        self._current_category = category
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)
        self._current_page = 0
        self._refresh_page()

    # ------------------------------------------------------------------
    # Pagination + rendering
    # ------------------------------------------------------------------

    def _refresh_page(self) -> None:
        """Re-render the tree for the current filter/page."""
        page_items, self._total_pages = filter_and_page(
            self._all_items,
            self._search_query,
            self._current_category,
            self._current_page,
        )

        # Disconnect itemChanged during bulk rebuild
        self._tree.itemChanged.disconnect(self._on_item_toggled)
        self._tree.clear()

        for row in page_items:
            mod_name = row["mod_name"]
            is_installed = row["is_installed"]
            is_enabled = mod_name not in self._staged_disabled

            tree_item = QTreeWidgetItem()
            tree_item.setData(0, Qt.ItemDataRole.UserRole, mod_name)

            # Checkbox column (col 0) — no text, just check state
            tree_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            tree_item.setCheckState(
                0,
                Qt.CheckState.Checked if is_enabled else Qt.CheckState.Unchecked,
            )

            # Mod name (col 1)
            tree_item.setText(1, row["title"])
            if not is_installed:
                from PySide6.QtGui import QColor
                tree_item.setForeground(1, QColor("#888"))

            # Version (col 2)
            tree_item.setText(2, row["version"])

            # Status chip (col 3)
            if not is_installed:
                tree_item.setText(3, "Not Downloaded")
                from PySide6.QtGui import QColor
                tree_item.setForeground(3, QColor("#9c27b0"))
            elif not is_enabled:
                tree_item.setText(3, "Disabled")
                from PySide6.QtGui import QColor
                tree_item.setForeground(3, QColor("#ff9800"))
            else:
                tree_item.setText(3, "Enabled")
                from PySide6.QtGui import QColor
                tree_item.setForeground(3, QColor("#4caf50"))

            self._tree.addTopLevelItem(tree_item)

            # Download button for not-installed rows (col 4)
            if not is_installed:
                dl_btn = QPushButton("Download")
                dl_btn.setFixedHeight(22)
                dl_btn.setObjectName("downloadChipButton")
                dl_btn.setStyleSheet(
                    "background:#9c27b0; color:#fff; border-radius:3px;"
                    "font-size:11px; padding:0 6px; border:none;"
                )
                dl_btn.clicked.connect(lambda _=False, n=mod_name: self._on_download_click(n))
                self._tree.setItemWidget(tree_item, 4, dl_btn)

        self._tree.itemChanged.connect(self._on_item_toggled)

        # Update pagination controls
        safe_page = max(0, min(self._current_page, self._total_pages - 1))
        self._page_label.setText(f"Page {safe_page + 1} of {self._total_pages}")
        self._prev_btn.setEnabled(safe_page > 0)
        self._next_btn.setEnabled(safe_page < self._total_pages - 1)

    # ------------------------------------------------------------------
    # Interaction handlers
    # ------------------------------------------------------------------

    def _on_item_toggled(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        mod_name = item.data(0, Qt.ItemDataRole.UserRole)
        if mod_name is None:
            return

        checked = item.checkState(0) == Qt.CheckState.Checked

        if checked:
            # User is enabling the mod in the profile
            self._staged_disabled.discard(mod_name)
            self._auto_resolve_deps(mod_name)
        else:
            # User is disabling the mod in the profile
            self._staged_disabled.add(mod_name)

        # Refresh to update status chips (rebuild items list first)
        self._build_all_items()
        self._refresh_page()

    def _auto_resolve_deps(self, mod_name: str) -> None:
        """When a mod is enabled, ensure its required deps are in the profile."""
        to_add, to_unblock, to_download = resolve_dep_additions(
            mod_name,
            set(self._staged_desired),
            self._staged_disabled,
            self._installed_mods,
        )

        changed = False
        for dep in to_add:
            if dep not in self._staged_desired:
                self._staged_desired.append(dep)
                changed = True

        for dep in to_unblock:
            self._staged_disabled.discard(dep)
            changed = True

        if to_download:
            names_str = ", ".join(f"<b>{d}</b>" for d in to_download)
            reply = QMessageBox.question(
                self,
                "Missing Dependencies",
                f"The following required dependencies for <b>{mod_name}</b> are not "
                f"installed:<br>{names_str}<br><br>Add them to the download queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Stage the dependencies into the profile before emitting download_requested
                for dep in to_download:
                    if dep not in self._staged_desired:
                        self._staged_desired.append(dep)
                        # Mark as disabled since it's not downloaded yet
                        self._staged_disabled.add(dep)
                        changed = True
                self.download_requested.emit(to_download)

        if changed:
            self._build_all_items()
            self._refresh_category_tabs()

    def _on_download_click(self, mod_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Download Mod",
            f"Add <b>{mod_name}</b> and its required dependencies to the download queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.download_requested.emit([mod_name])

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        mod_name = item.data(0, Qt.ItemDataRole.UserRole)
        if not mod_name:
            return
        menu = QMenu(self)
        remove_action = menu.addAction(f"Remove '{mod_name}' from Profile")
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen == remove_action:
            self._remove_from_profile(mod_name)

    def _remove_from_profile(self, mod_name: str) -> None:
        if mod_name in self._staged_desired:
            self._staged_desired.remove(mod_name)
        self._staged_disabled.discard(mod_name)
        self._build_all_items()
        self._refresh_category_tabs()
        self._current_page = 0
        self._refresh_page()

    def _on_prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_page()

    def _on_next_page(self) -> None:
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._refresh_page()

    def _on_search_commit(self) -> None:
        self._search_query = self._search_edit.text()
        self._current_page = 0
        self._refresh_page()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        self._profile.desired_mods = list(self._staged_desired)
        self._profile.disabled_in_profile = sorted(self._staged_disabled)
        try:
            self._profile_store.save(self._profile)
        except Exception as exc:
            logger.warning("Could not save profile: %s", exc)
            QMessageBox.warning(self, "Save Failed", f"Could not save profile:\n{exc}")
            return
        self.accept()