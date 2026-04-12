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


# ---------------------------------------------------------------------------
# Test 4: dependency-aware build_diff
# ---------------------------------------------------------------------------

def _make_mod(name: str, required_deps: list[str] | None = None):
    """Return a minimal Mod-like object with raw_data deps."""
    from factorio_mod_manager.core.mod import Mod
    deps = list(required_deps or [])
    return Mod(
        name=name,
        title=name,
        version="1.0.0",
        author="Test",
        raw_data={"dependencies": deps},
    )


def test_diff_does_not_download_base() -> None:
    """base has no ZIP file; it must never appear as a DOWNLOAD item."""
    profile = Profile(id="p1", name="Test", desired_mods=["base", "my-mod"])
    diff = build_diff(
        profile,
        installed_zip_names=["my-mod"],   # no base.zip — realistic
        current_enabled={"my-mod": True},
    )
    assert not any(i.mod_name == "base" for i in diff.items), (
        "base should never appear in a diff"
    )


def test_diff_does_not_disable_required_dep_of_desired_mod() -> None:
    """flib is a required dep of my-lib; it must not be disabled even if not in the profile."""
    flib = _make_mod("flib")
    my_lib = _make_mod("my-lib", required_deps=["flib >= 1.0"])
    mods = {"flib": flib, "my-lib": my_lib}

    profile = Profile(id="p1", name="Test", desired_mods=["my-lib"])
    diff = build_diff(
        profile,
        installed_zip_names=["flib", "my-lib"],
        current_enabled={"flib": True, "my-lib": True},
        installed_mods=mods,
    )
    assert not any(
        i.action == DiffAction.DISABLE and i.mod_name == "flib" for i in diff.items
    ), "flib is a required dep of my-lib and must not be disabled"


def test_diff_disables_optional_dep_not_in_profile() -> None:
    """An optional dep that is not in the profile IS safe to disable."""
    helper = _make_mod("optional-helper")
    my_lib = _make_mod("my-lib", required_deps=["? optional-helper"])
    mods = {"optional-helper": helper, "my-lib": my_lib}

    profile = Profile(id="p1", name="Test", desired_mods=["my-lib"])
    diff = build_diff(
        profile,
        installed_zip_names=["optional-helper", "my-lib"],
        current_enabled={"optional-helper": True, "my-lib": True},
        installed_mods=mods,
    )
    assert any(
        i.action == DiffAction.DISABLE and i.mod_name == "optional-helper" for i in diff.items
    ), "optional dep not in profile should be disabled"


def test_diff_protects_transitive_required_dep() -> None:
    """A -> B -> C (all required): applying profile with only A must keep B and C enabled."""
    mod_c = _make_mod("mod-c")
    mod_b = _make_mod("mod-b", required_deps=["mod-c"])
    mod_a = _make_mod("mod-a", required_deps=["mod-b"])
    mods = {"mod-a": mod_a, "mod-b": mod_b, "mod-c": mod_c}

    profile = Profile(id="p1", name="Test", desired_mods=["mod-a"])
    diff = build_diff(
        profile,
        installed_zip_names=["mod-a", "mod-b", "mod-c"],
        current_enabled={"mod-a": True, "mod-b": True, "mod-c": True},
        installed_mods=mods,
    )
    disabled = {i.mod_name for i in diff.items if i.action == DiffAction.DISABLE}
    assert "mod-b" not in disabled, "mod-b is a required dep (transitive) and must be kept"
    assert "mod-c" not in disabled, "mod-c is a required dep (transitive) and must be kept"


# ---------------------------------------------------------------------------
# Test 5: disabled_in_profile field
# ---------------------------------------------------------------------------

def test_disabled_in_profile_generates_disable_action() -> None:
    """A mod that is in desired_mods AND disabled_in_profile should be DISABLED on apply."""
    profile = Profile(
        id="p1",
        name="Test",
        desired_mods=["my-mod"],
        disabled_in_profile=["my-mod"],
    )
    diff = build_diff(
        profile,
        installed_zip_names=["my-mod"],
        current_enabled={"my-mod": True},
    )
    assert any(
        i.action == DiffAction.DISABLE and i.mod_name == "my-mod" for i in diff.items
    ), "mod in disabled_in_profile that is currently enabled should get DISABLE action"


def test_disabled_in_profile_excluded_from_enable() -> None:
    """A mod in disabled_in_profile must NOT get an ENABLE action even if currently disabled."""
    profile = Profile(
        id="p1",
        name="Test",
        desired_mods=["my-mod"],
        disabled_in_profile=["my-mod"],
    )
    diff = build_diff(
        profile,
        installed_zip_names=["my-mod"],
        current_enabled={"my-mod": False},
    )
    assert not any(
        i.action == DiffAction.ENABLE and i.mod_name == "my-mod" for i in diff.items
    ), "mod in disabled_in_profile must not be enabled by the diff"
    # Also must not be downloaded
    assert not any(
        i.action == DiffAction.DOWNLOAD and i.mod_name == "my-mod" for i in diff.items
    )


def test_disabled_in_profile_deps_not_protected_in_safe_set() -> None:
    """Required dep of a disabled profile mod is NOT in the safe_set, so it can be disabled."""
    flib = _make_mod("flib")
    my_lib = _make_mod("my-lib", required_deps=["flib"])
    mods = {"flib": flib, "my-lib": my_lib}

    # my-lib is in profile but disabled; flib is its required dep but not in profile
    profile = Profile(
        id="p1",
        name="Test",
        desired_mods=["my-lib"],
        disabled_in_profile=["my-lib"],
    )
    diff = build_diff(
        profile,
        installed_zip_names=["flib", "my-lib"],
        current_enabled={"flib": True, "my-lib": True},
        installed_mods=mods,
    )
    disabled = {i.mod_name for i in diff.items if i.action == DiffAction.DISABLE}
    # flib should be disabled because my-lib (its only consumer) is disabled in profile
    assert "flib" in disabled, (
        "flib should be disabled — its only dependent (my-lib) is disabled_in_profile"
    )


def test_profile_serialization_includes_disabled_in_profile() -> None:
    """Profile.to_dict() and from_dict() round-trip disabled_in_profile."""
    profile = Profile(
        id="p1",
        name="Test",
        desired_mods=["mod-a", "mod-b"],
        disabled_in_profile=["mod-b"],
    )
    d = profile.to_dict()
    assert d["disabled_in_profile"] == ["mod-b"]

    loaded = Profile.from_dict(d)
    assert loaded.disabled_in_profile == ["mod-b"]


def test_profile_from_dict_backward_compat_missing_disabled_field() -> None:
    """Old profiles without disabled_in_profile key parse without error."""
    d = {"id": "p1", "name": "Old Profile", "desired_mods": ["mod-a"]}
    loaded = Profile.from_dict(d)
    assert loaded.disabled_in_profile == []
