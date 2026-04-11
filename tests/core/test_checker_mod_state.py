"""Tests for Checker enabled-state via .zip.bak rename strategy.

Design:
  - scan_mods() globs both *.zip (enabled) and *.zip.bak (disabled).
  - disable_mod() renames modname_version.zip  -> modname_version.zip.bak
  - enable_mod()  renames modname_version.zip.bak -> modname_version.zip
  - mod-list.json is never read or written by these paths.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from factorio_mod_manager.core.checker import ModChecker
from factorio_mod_manager.ui.checker_logic import CheckerLogic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(folder: Path, name: str, version: str, *, disabled: bool = False) -> Path:
    """Create a minimal valid mod ZIP (or .zip.bak) in *folder*."""
    suffix = ".zip.bak" if disabled else ".zip"
    path = folder / f"{name}_{version}{suffix}"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            f"{name}_{version}/info.json",
            json.dumps({"name": name, "version": version, "title": name, "author": "Test"}),
        )
    return path


# ---------------------------------------------------------------------------
# scan_mods() — picks up both .zip and .zip.bak
# ---------------------------------------------------------------------------


class TestScanEnabledState:
    def test_zip_files_are_scanned_as_enabled(self, tmp_path):
        _make_zip(tmp_path, "mod_a", "1.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()
        assert mods["mod_a"].enabled is True

    def test_zip_bak_files_are_scanned_as_disabled(self, tmp_path):
        _make_zip(tmp_path, "mod_b", "2.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()
        assert "mod_b" in mods
        assert mods["mod_b"].enabled is False

    def test_scan_handles_mix_of_enabled_and_disabled(self, tmp_path):
        _make_zip(tmp_path, "mod_a", "1.0.0")
        _make_zip(tmp_path, "mod_b", "2.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()
        assert mods["mod_a"].enabled is True
        assert mods["mod_b"].enabled is False

    def test_scan_stores_bak_path_in_file_path(self, tmp_path):
        _make_zip(tmp_path, "mod_c", "1.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            mods = checker.scan_mods()
        assert mods["mod_c"].file_path.endswith(".zip.bak")


# ---------------------------------------------------------------------------
# disable_mod() — renames .zip -> .zip.bak, ZIP content preserved
# ---------------------------------------------------------------------------


class TestDisableMod:
    def test_disable_renames_zip_to_zip_bak(self, tmp_path):
        _make_zip(tmp_path, "mod_x", "1.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")

        assert not (tmp_path / "mod_x_1.0.0.zip").exists()
        assert (tmp_path / "mod_x_1.0.0.zip.bak").exists()

    def test_disable_updates_in_memory_enabled_flag(self, tmp_path):
        _make_zip(tmp_path, "mod_x", "1.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")

        assert checker.mods["mod_x"].enabled is False

    def test_disable_updates_file_path_to_bak(self, tmp_path):
        _make_zip(tmp_path, "mod_x", "1.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")

        assert checker.mods["mod_x"].file_path.endswith(".zip.bak")

    def test_disable_is_idempotent_on_already_disabled(self, tmp_path):
        """Calling disable_mod on an already-.zip.bak file does nothing."""
        _make_zip(tmp_path, "mod_x", "1.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_x")  # should not raise

        assert (tmp_path / "mod_x_1.0.0.zip.bak").exists()


# ---------------------------------------------------------------------------
# enable_mod() — renames .zip.bak -> .zip
# ---------------------------------------------------------------------------


class TestEnableMod:
    def test_enable_renames_zip_bak_to_zip(self, tmp_path):
        _make_zip(tmp_path, "mod_y", "1.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.enable_mod("mod_y")

        assert (tmp_path / "mod_y_1.0.0.zip").exists()
        assert not (tmp_path / "mod_y_1.0.0.zip.bak").exists()

    def test_enable_updates_in_memory_enabled_flag(self, tmp_path):
        _make_zip(tmp_path, "mod_y", "1.0.0", disabled=True)
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.enable_mod("mod_y")

        assert checker.mods["mod_y"].enabled is True

    def test_enable_is_idempotent_on_already_active(self, tmp_path):
        """Calling enable_mod on an already-.zip file does nothing."""
        _make_zip(tmp_path, "mod_y", "1.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.enable_mod("mod_y")  # should not raise

        assert (tmp_path / "mod_y_1.0.0.zip").exists()

    def test_roundtrip_disable_then_enable(self, tmp_path):
        """Disable then re-enable returns file to original .zip name."""
        original = _make_zip(tmp_path, "mod_z", "3.0.0")
        checker = ModChecker(str(tmp_path))
        with patch.object(checker.portal, "get_mod", return_value=None):
            checker.scan_mods()

        logic = CheckerLogic(checker, lambda msg, level="INFO": None)
        logic.disable_mod("mod_z")
        logic.enable_mod("mod_z")

        assert (tmp_path / "mod_z_3.0.0.zip").exists()
        assert not (tmp_path / "mod_z_3.0.0.zip.bak").exists()
        assert checker.mods["mod_z"].enabled is True


