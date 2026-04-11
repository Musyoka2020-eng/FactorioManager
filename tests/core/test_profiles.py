"""Tests for profile domain models and ProfileStore."""
import pytest
from pathlib import Path
from factorio_mod_manager.core.profiles import (
    Profile,
    PresetFamily,
    PresetSeed,
    ProfileDiff,
    ProfileDiffItem,
    ProfileSnapshot,
    ProfileStore,
    CURATED_PRESETS,
    DiffAction,
    build_diff,
)


@pytest.fixture
def profile_store(tmp_path: Path) -> ProfileStore:
    return ProfileStore(profiles_dir=tmp_path / "profiles")


# ---------------------------------------------------------------------------
# Test 1: saving current state creates named profile from enabled mod names
# ---------------------------------------------------------------------------

def test_profile_from_enabled_state_uses_mod_names_not_zip_filenames() -> None:
    enabled_mods = ["base", "my-mod", "another-mod"]
    profile = Profile.from_enabled_state("My Setup", enabled_mods)
    assert profile.name == "My Setup"
    assert set(profile.desired_mods) == {"base", "my-mod", "another-mod"}
    assert profile.id  # has an ID


def test_profile_from_enabled_state_strips_name() -> None:
    profile = Profile.from_enabled_state("  trimmed  ", ["base"])
    assert profile.name == "trimmed"


def test_profile_from_enabled_state_raises_on_empty_name() -> None:
    with pytest.raises(ValueError):
        Profile.from_enabled_state("", ["base"])


def test_profile_store_save_and_load(profile_store: ProfileStore) -> None:
    profile = Profile.from_enabled_state("My Profile", ["base", "my-mod"])
    profile_store.save(profile)
    loaded = profile_store.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "My Profile"
    assert "my-mod" in loaded[0].desired_mods


# ---------------------------------------------------------------------------
# Test 2: curated preset families are exactly Vanilla+, QoL, and Logistics and Rail
# ---------------------------------------------------------------------------

def test_curated_presets_have_exactly_three_families() -> None:
    families = {p.family for p in CURATED_PRESETS}
    assert families == {PresetFamily.VANILLA_PLUS, PresetFamily.QOL, PresetFamily.LOGISTICS_AND_RAIL}


def test_curated_preset_vanilla_plus_exists() -> None:
    names = [p.family.value for p in CURATED_PRESETS]
    assert "Vanilla+" in names


def test_curated_preset_qol_exists() -> None:
    names = [p.family.value for p in CURATED_PRESETS]
    assert "QoL" in names


def test_curated_preset_logistics_and_rail_exists() -> None:
    names = [p.family.value for p in CURATED_PRESETS]
    assert "Logistics and Rail" in names


def test_preset_to_profile_creates_profile_with_family_name() -> None:
    preset = next(p for p in CURATED_PRESETS if p.family == PresetFamily.QOL)
    profile = preset.to_profile()
    assert profile.name == "QoL"
    assert "base" in profile.desired_mods


# ---------------------------------------------------------------------------
# Test 3: diff generation returns explicit action types plus undo snapshot payload
# ---------------------------------------------------------------------------

def test_diff_returns_download_for_missing_mod() -> None:
    profile = Profile(id="p1", name="Test", desired_mods=["base", "missing-mod"])
    diff = build_diff(profile, installed_zip_names=["base"], current_enabled={"base": True})
    assert any(i.action == DiffAction.DOWNLOAD and i.mod_name == "missing-mod" for i in diff.items)


def test_diff_returns_enable_for_installed_disabled_mod() -> None:
    profile = Profile(id="p1", name="Test", desired_mods=["base", "my-mod"])
    diff = build_diff(
        profile,
        installed_zip_names=["base", "my-mod"],
        current_enabled={"base": True, "my-mod": False},
    )
    assert any(i.action == DiffAction.ENABLE and i.mod_name == "my-mod" for i in diff.items)


def test_diff_returns_disable_for_enabled_mod_not_in_profile() -> None:
    profile = Profile(id="p1", name="Test", desired_mods=["base"])
    diff = build_diff(
        profile,
        installed_zip_names=["base", "extra-mod"],
        current_enabled={"base": True, "extra-mod": True},
    )
    assert any(i.action == DiffAction.DISABLE and i.mod_name == "extra-mod" for i in diff.items)


def test_diff_is_empty_when_state_matches_profile() -> None:
    profile = Profile(id="p1", name="Test", desired_mods=["base"])
    diff = build_diff(
        profile,
        installed_zip_names=["base"],
        current_enabled={"base": True},
    )
    assert diff.is_empty


def test_diff_has_correct_counters() -> None:
    profile = Profile(id="p1", name="Test", desired_mods=["base", "new-mod"])
    diff = build_diff(
        profile,
        installed_zip_names=["base", "old-mod", "disabled-mod"],
        current_enabled={"base": True, "old-mod": True, "disabled-mod": False},
    )
    assert diff.download_count == 1   # new-mod not installed
    assert diff.disable_count == 1    # old-mod installed+enabled but not in profile
    # disabled-mod is in installed but not in desired and NOT in currently enabled → no disable action


def test_snapshot_serialization_round_trip() -> None:
    snap = ProfileSnapshot(
        id="snap-1",
        profile_id="prof-1",
        profile_name="Test",
        enabled_before={"base": True, "my-mod": False},
        valid=True,
    )
    data = snap.to_dict()
    loaded = ProfileSnapshot.from_dict(data)
    assert loaded.id == snap.id
    assert loaded.enabled_before == snap.enabled_before
    assert loaded.valid is True


def test_snapshot_invalidation(profile_store: ProfileStore) -> None:
    snap = ProfileSnapshot(
        id="snap-2",
        profile_id="prof-1",
        profile_name="Test",
        enabled_before={"base": True},
        valid=True,
    )
    profile_store.save_snapshot(snap)
    profile_store.invalidate_snapshot("snap-2")
    loaded = profile_store.load_snapshot("snap-2")
    assert loaded is not None
    assert loaded.valid is False
