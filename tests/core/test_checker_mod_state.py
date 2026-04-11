"""TDD tests for Checker enabled-state merging and toggle helpers.

Covers:
  1. scan_mods() merges mod-list.json enabled flags into Mod.enabled
  2. disable_mod() writes mod-list.json without deleting the ZIP
  3. enable_mod() updates mod-list.json state
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


def _write_mod_list(folder: Path, entries: dict) -> None:
    data = {"mods": [{"name": k, "enabled": v} for k, v in entries.items()]}
    (folder / "mod-list.json").write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: scan_mods() merges enabled flags
# ---------------------------------------------------------------------------


class TestScanMergesEnabledState:
    def test_scan_merges_enabled_and_disabled_from_mod_list_json(self, tmp_path):
        """Installed mods get their enabled flag from mod-list.json."""
        _make_zip(tmp_path, "mod_a", "1.0.0")
        _make_zip(tmp_path, "mod_b", "2.0.0")
        _write_mod_list(tmp_path, {"mod_a": True, "mod_b": False})

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        assert mods["mod_a"].enabled is True
        assert mods["mod_b"].enabled is False

    def test_scan_defaults_missing_entries_to_enabled(self, tmp_path):
        """Mods absent from mod-list.json are treated as enabled by default."""
        _make_zip(tmp_path, "mod_c", "1.0.0")
        _write_mod_list(tmp_path, {})  # mod_c not in the file

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        assert mods["mod_c"].enabled is True

    def test_scan_handles_missing_mod_list_gracefully(self, tmp_path):
        """scan_mods() completes without error when mod-list.json is absent."""
        _make_zip(tmp_path, "mod_d", "1.0.0")
        # No mod-list.json created

        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()

        # Defaults to enabled when file is missing
        assert mods["mod_d"].enabled is True


# ---------------------------------------------------------------------------
# Test 2: disable_mod() — writes mod-list.json, ZIP untouched
# ---------------------------------------------------------------------------


class TestDisableMod:
    def test_disable_writes_false_to_mod_list_json(self, tmp_path):
        """disable_mod() sets the mod's enabled flag to False in mod-list.json."""
        _make_zip(tmp_path, "mod_x", "1.0.0")
        _write_mod_list(tmp_path, {"mod_x": True})

        checker = ModChecker(str(tmp_path))
        from factorio_mod_manager.ui.checker_logic import CheckerLogic

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")

        data = json.loads((tmp_path / "mod-list.json").read_text())
        enabled_map = {e["name"]: e["enabled"] for e in data["mods"]}
        assert enabled_map.get("mod_x") is False

    def test_disable_does_not_delete_zip(self, tmp_path):
        """ZIP must remain on disk after disabling (D-15)."""
        _make_zip(tmp_path, "mod_x", "1.0.0")
        _write_mod_list(tmp_path, {"mod_x": True})

        checker = ModChecker(str(tmp_path))
        from factorio_mod_manager.ui.checker_logic import CheckerLogic

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")

        assert (tmp_path / "mod_x_1.0.0.zip").exists()


# ---------------------------------------------------------------------------
# Test 3: enable_mod() — updates state
# ---------------------------------------------------------------------------


class TestEnableMod:
    def test_enable_updates_mod_list_json_to_true(self, tmp_path):
        """enable_mod() sets the mod's enabled flag to True in mod-list.json."""
        _make_zip(tmp_path, "mod_y", "1.0.0")
        _write_mod_list(tmp_path, {"mod_y": False})

        checker = ModChecker(str(tmp_path))
        from factorio_mod_manager.ui.checker_logic import CheckerLogic

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.enable_mod("mod_y")

        data = json.loads((tmp_path / "mod-list.json").read_text())
        enabled_map = {e["name"]: e["enabled"] for e in data["mods"]}
        assert enabled_map.get("mod_y") is True

    def test_enable_updates_in_memory_checker_mods(self, tmp_path):
        """enable_mod() immediately updates the in-memory Mod.enabled field."""
        _make_zip(tmp_path, "mod_z", "1.0.0")
        _write_mod_list(tmp_path, {"mod_z": False})

        checker = ModChecker(str(tmp_path))
        from factorio_mod_manager.ui.checker_logic import CheckerLogic

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        # Pre-populate the in-memory mods dict with a disabled entry
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()
        assert checker.mods["mod_z"].enabled is False

        logic.enable_mod("mod_z")
        assert checker.mods["mod_z"].enabled is True
