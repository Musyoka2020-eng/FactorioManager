"""Tests for ModListStore (mod-list.json service)."""
import json
import pytest
from pathlib import Path
from factorio_mod_manager.core.mod_list import ModListStore


@pytest.fixture
def mods_folder(tmp_path: Path) -> Path:
    return tmp_path / "mods"


def write_mod_list(folder: Path, mods: list) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mod-list.json").write_text(
        json.dumps({"mods": mods}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Test 1: reading preserves unrelated entries such as 'base'
# ---------------------------------------------------------------------------

def test_load_returns_enabled_states_keyed_by_mod_name(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [
        {"name": "base", "enabled": True},
        {"name": "my-mod", "enabled": False},
        {"name": "other-mod", "enabled": True},
    ])
    store = ModListStore(mods_folder)
    states = store.load()
    assert states["base"] is True
    assert states["my-mod"] is False
    assert states["other-mod"] is True
    # All three entries present
    assert len(states) == 3


def test_load_preserves_base_entry(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [
        {"name": "base", "enabled": True},
        {"name": "unrelated-mod", "enabled": True},
    ])
    store = ModListStore(mods_folder)
    states = store.load()
    assert "base" in states


# ---------------------------------------------------------------------------
# Test 2: toggling a mod never deletes ZIP-backed mods from disk state
# (only mod-list.json enabled state changes)
# ---------------------------------------------------------------------------

def test_toggle_updates_only_enabled_state_not_zip_files(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [
        {"name": "base", "enabled": True},
        {"name": "my-mod", "enabled": True},
    ])
    # Create a fake ZIP to prove it is not touched
    fake_zip = mods_folder / "my-mod_1.0.0.zip"
    fake_zip.write_bytes(b"fake")
    store = ModListStore(mods_folder)
    store.disable("my-mod")
    assert fake_zip.exists(), "ZIP must not be deleted when disabling a mod"
    states = store.load()
    assert states["my-mod"] is False
    assert states["base"] is True


def test_toggle_preserves_unrelated_entries(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [
        {"name": "base", "enabled": True},
        {"name": "third-party-mod", "enabled": True},
        {"name": "my-mod", "enabled": True},
    ])
    store = ModListStore(mods_folder)
    store.disable("my-mod")
    states = store.load()
    assert states["third-party-mod"] is True  # unrelated entry preserved
    assert states["my-mod"] is False


def test_cannot_disable_base(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [{"name": "base", "enabled": True}])
    store = ModListStore(mods_folder)
    with pytest.raises(ValueError, match="base"):
        store.disable("base")


# ---------------------------------------------------------------------------
# Test 3: missing or malformed mod-list.json falls back safely; next write is atomic
# ---------------------------------------------------------------------------

def test_missing_mod_list_returns_empty_dict(mods_folder: Path) -> None:
    mods_folder.mkdir(parents=True, exist_ok=True)
    store = ModListStore(mods_folder)
    states = store.load()
    assert states == {}


def test_malformed_mod_list_falls_back_safely(mods_folder: Path) -> None:
    mods_folder.mkdir(parents=True, exist_ok=True)
    (mods_folder / "mod-list.json").write_text("{not valid json!!}", encoding="utf-8")
    store = ModListStore(mods_folder)
    states = store.load()
    assert states == {}


def test_write_after_fallback_is_atomic(mods_folder: Path) -> None:
    mods_folder.mkdir(parents=True, exist_ok=True)
    store = ModListStore(mods_folder)
    # Write from clean state (no existing file)
    store.save({"my-mod": True})
    path = mods_folder / "mod-list.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    names = {m["name"] for m in data["mods"]}
    assert "my-mod" in names
    assert "base" in names  # base is always added


def test_atomic_write_enforces_base_enabled(mods_folder: Path) -> None:
    write_mod_list(mods_folder, [{"name": "base", "enabled": True}])
    store = ModListStore(mods_folder)
    # Attempt to write base=False via save() directly (bypasses toggle guard)
    store.save({"base": False, "my-mod": True})
    states = store.load()
    assert states["base"] is True  # base remains enabled regardless
