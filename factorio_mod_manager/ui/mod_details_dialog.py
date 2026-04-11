"""Mod details popup dialog — Phase 3."""
from __future__ import annotations

from typing import Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import Mod, ModStatus


# Status display mapping (matches CheckerPresenter.STATUS_COLORS)
_STATUS_DISPLAY = {
    ModStatus.UP_TO_DATE: ("\u2713 Up to date", "#4ec952"),
    ModStatus.OUTDATED:   ("\u2b06 Outdated",   "#ffad00"),
    ModStatus.UNKNOWN:    ("? Unknown",          "#b0b0b0"),
    ModStatus.ERROR:      ("\u2717 Error",        "#d13438"),
}


class ModDetailsDialog(QDialog):
    """Modal dialog showing details for a mod.

    Accepts either a Mod dataclass instance (for installed mods) or a
    portal result dict (for portal search results).

    Args:
        data: Mod dataclass or portal dict
              ({"name","title","owner","summary","downloads_count","releases"})
        source: "installed" | "portal" — used to choose CTA label
        parent: parent widget (should be QMainWindow)
    """

    def __init__(
        self,
        data: Union[Mod, dict],
        source: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumSize(520, 400)
        self.setModal(True)

        if isinstance(data, Mod):
            self._name = data.name
            self._title = data.title or data.name
            self._author = data.author or ""
            self._version = data.version or ""
            self._description = data.description or ""
            self._downloads: int | None = data.downloads or None
            self._status: ModStatus | None = data.status
            self._latest_version: str | None = getattr(data, "latest_version", None)
        else:
            self._name = data.get("name", "")
            self._title = data.get("title") or self._name
            self._author = data.get("owner", "")
            releases = data.get("releases", [])
            self._version = releases[-1].get("version", "") if releases else ""
            self._description = data.get("summary", "") or data.get("description", "")
            downloads = data.get("downloads_count")
            self._downloads = int(downloads) if downloads else None
            self._status = None
            self._latest_version = None

        self._source = source
        self.setWindowTitle(self._title)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(8)

        # Title
        title_lbl = QLabel(self._title)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        title_lbl.setWordWrap(True)
        root.addWidget(title_lbl)

        # Author / version / downloads row
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

        # Status badge (installed mods only)
        if self._status is not None:
            status_text, color = _STATUS_DISPLAY.get(
                self._status, ("? Unknown", "#b0b0b0")
            )
            status_lbl = QLabel(status_text)
            status_lbl.setTextFormat(Qt.TextFormat.PlainText)
            status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            root.addWidget(status_lbl)

            # Show latest version if outdated
            if self._status == ModStatus.OUTDATED and self._latest_version:
                latest_lbl = QLabel(f"Latest: v{self._latest_version}")
                latest_lbl.setTextFormat(Qt.TextFormat.PlainText)
                root.addWidget(latest_lbl)

        # Description text area
        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setPlainText(self._description or "No description available.")
        root.addWidget(desc_edit, stretch=1)

        # Footer
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(8)

        # Context action button
        if self._source == "portal":
            cta_label = "View on Portal"
        else:
            cta_label = "Check for Updates"
        cta_btn = QPushButton(cta_label)
        cta_btn.setObjectName("accentButton")
        cta_btn.clicked.connect(self._on_cta)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        footer_layout.addWidget(cta_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        root.addWidget(footer)

    def _on_cta(self) -> None:
        """Open mod portal page in browser (portal source) or do nothing (installed)."""
        if self._source == "portal" and self._name:
            import webbrowser
            webbrowser.open(f"https://mods.factorio.com/mod/{self._name}")
        self.accept()
