"""Tests for Checker enabled-state behaviour (new design: no mod-list.json writes).

New design:
  - scan_mods() always returns mods with enabled=True (Mod dataclass default).
  - Enabled/disabled state is tracked in-memory in the UI layer only.
  - mod-list.json is never written to by the enable/disable toggle path.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from factorio_mod_manager.core.checker import ModChecker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(folder: Path, name: str, version: str) -> Path:
    """Create a minimal valid mod ZIP in *folder*."""
    path = folder / f"{name}_{version}.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            f"{name}_{version}/info.json",
            json.dumps({"name": name, "version": version, "title": name, "author": "Test"}),
        )
    return path


# ---------------------------------------------------------------------------
# scan_mods() — enabled defaults
# ---------------------------------------------------------------------------


class TestScanEnabledDefaults:
    def test_scan_sets_all_mods_enabled_by_default(self, tmp_path):
        """scan_mods() returns every mod with enabled=True (Mod dataclass default)."""
        _make_zip(tmp_path, "mod_a", "1.0.0")
        _make_zip(tmp_path, "mod_b", "2.0.0")

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        assert mods["mod_a"].enabled is True
        assert mods["mod_b"].enabled is True

    def test_scan_does_not_require_mod_list_json(self, tmp_path):
        """scan_mods() succeeds even when mod-list.json is absent."""
        _make_zip(tmp_path, "mod_c", "1.0.0")
        # No mod-list.json

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        assert "mod_c" in mods
        assert mods["mod_c"].enabled is True

    def test_scan_ignores_existing_mod_list_json(self, tmp_path):
        """scan_mods() does NOT read mod-list.json — enabled state is always True from scan."""
        _make_zip(tmp_path, "mod_d", "1.0.0")
        # Write a mod-list.json that marks mod_d as disabled — scan must ignore it
        (tmp_path / "mod-list.json").write_text(
            json.dumps({"mods": [{"name": "mod_d", "enabled": False}]}),
            encoding="utf-8",
        )

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        # scan_mods no longer reads mod-list.json; enabled is always True
        assert mods["mod_d"].enabled is True


# ---------------------------------------------------------------------------
# In-memory enabled-state toggling
# ---------------------------------------------------------------------------


class TestInMemoryEnabledState:
    def test_mod_enabled_field_can_be_set_in_memory(self, tmp_path):
        """Mod.enabled can be updated in-memory without touching any file."""
        _make_zip(tmp_path, "mod_e", "1.0.0")

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        assert mods["mod_e"].enabled is True
        # Simulate what the UI layer does when the checkbox is toggled
        mods["mod_e"].enabled = False
        assert mods["mod_e"].enabled is False
        # ZIP must still exist
        assert (tmp_path / "mod_e_1.0.0.zip").exists()

    def test_toggle_does_not_touch_mod_list_json(self, tmp_path):
        """Setting Mod.enabled in-memory never modifies mod-list.json."""
        _make_zip(tmp_path, "mod_f", "1.0.0")
        mod_list_path = tmp_path / "mod-list.json"
        original_content = json.dumps({"mods": [{"name": "base", "enabled": True}]})
        mod_list_path.write_text(original_content, encoding="utf-8")

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        # Toggle in-memory
        mods["mod_f"].enabled = False

        # mod-list.json must be unchanged
        assert mod_list_path.read_text(encoding="utf-8") == original_content

