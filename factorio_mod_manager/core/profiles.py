"""Profile persistence and diff domain models for Factorio Mod Manager.

A *Profile* represents a desired enabled-mod set (not raw ZIP filenames).
A *ProfileDiff* describes the exact actions required to reach that desired
state from the current installed + enabled state.
A *ProfileSnapshot* captures the pre-apply state so callers can restore it.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..utils.config import Config


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DiffAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    ENABLE = "enable"
    DISABLE = "disable"
    DOWNLOAD = "download"


class PresetFamily(str, Enum):
    VANILLA_PLUS = "Vanilla+"
    QOL = "QoL"
    LOGISTICS_AND_RAIL = "Logistics and Rail"


# ---------------------------------------------------------------------------
# Core data objects (pure Python, no Qt imports)
# ---------------------------------------------------------------------------


@dataclass
class Profile:
    """Named profile storing a desired enabled-mod set."""

    id: str
    name: str
    # Complete list of mods that belong to this profile (both enabled and disabled).
    desired_mods: List[str] = field(default_factory=list)
    # Mods that are in the profile but the user has explicitly disabled.
    # They remain visible in the profile but will not be activated on apply.
    disabled_in_profile: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "desired_mods": self.desired_mods,
            "disabled_in_profile": self.disabled_in_profile,
        }

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        return Profile(
            id=d["id"],
            name=d["name"],
            desired_mods=d.get("desired_mods", []),
            disabled_in_profile=d.get("disabled_in_profile", []),
        )

    @staticmethod
    def from_enabled_state(name: str, enabled_mod_names: List[str]) -> "Profile":
        """Create a profile from the current enabled mod names."""
        if not name or not name.strip():
            raise ValueError("Profile name must not be empty.")
        return Profile(id=str(uuid.uuid4()), name=name.strip(), desired_mods=list(enabled_mod_names))


@dataclass
class PresetSeed:
    """A curated starter preset for seeding profiles."""

    family: PresetFamily
    description: str
    # Representative mod names for this preset family
    mod_names: List[str] = field(default_factory=list)

    def to_profile(self, name: Optional[str] = None) -> Profile:
        """Convert this preset into a Profile object."""
        return Profile(
            id=str(uuid.uuid4()),
            name=name or self.family.value,
            desired_mods=list(self.mod_names),
        )


@dataclass
class ProfileDiffItem:
    """A single line in a ProfileDiff."""

    action: DiffAction
    mod_name: str
    # Optional download URL hint for DOWNLOAD items
    download_url: Optional[str] = None


@dataclass
class ProfileDiff:
    """Immutable diff payload describing how to reach a profile target."""

    profile_id: str
    profile_name: str
    items: List[ProfileDiffItem] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience counters
    # ------------------------------------------------------------------

    def count(self, action: DiffAction) -> int:
        return sum(1 for i in self.items if i.action == action)

    @property
    def add_count(self) -> int:
        return self.count(DiffAction.ADD)

    @property
    def remove_count(self) -> int:
        return self.count(DiffAction.REMOVE)

    @property
    def enable_count(self) -> int:
        return self.count(DiffAction.ENABLE)

    @property
    def disable_count(self) -> int:
        return self.count(DiffAction.DISABLE)

    @property
    def download_count(self) -> int:
        return self.count(DiffAction.DOWNLOAD)

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


@dataclass
class ProfileSnapshot:
    """Pre-apply snapshot for one-click undo restore.

    Stores the enabled-state mapping captured *before* a profile apply
    so it can be restored atomically.
    """

    id: str
    profile_id: str
    profile_name: str
    # Mapping of mod_name -> was_enabled at capture time
    enabled_before: Dict[str, bool] = field(default_factory=dict)
    # Whether this snapshot is still eligible for undo
    valid: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "enabled_before": self.enabled_before,
            "valid": self.valid,
        }

    @staticmethod
    def from_dict(d: dict) -> "ProfileSnapshot":
        return ProfileSnapshot(
            id=d["id"],
            profile_id=d["profile_id"],
            profile_name=d["profile_name"],
            enabled_before=d.get("enabled_before", {}),
            valid=d.get("valid", True),
        )


# ---------------------------------------------------------------------------
# Curated presets
# ---------------------------------------------------------------------------

CURATED_PRESETS: List[PresetSeed] = [
    PresetSeed(
        family=PresetFamily.VANILLA_PLUS,
        description="Quality-of-life improvements that keep the vanilla experience.",
        mod_names=["base"],
    ),
    PresetSeed(
        family=PresetFamily.QOL,
        description="Popular quality-of-life mods for a smoother experience.",
        mod_names=["base"],
    ),
    PresetSeed(
        family=PresetFamily.LOGISTICS_AND_RAIL,
        description="Logistics bots and train management enhancements.",
        mod_names=["base"],
    ),
]


# ---------------------------------------------------------------------------
# ProfileDiff builder
# ---------------------------------------------------------------------------


# Mods that are never downloaded or disabled by profile apply.
_NEVER_DISABLE: frozenset = frozenset({"base"})


def _extract_required_dep_names(raw_dep_strings: List[str]) -> List[str]:
    """Return mod names for REQUIRED (non-optional, non-incompatible) deps.

    Factorio raw dep string prefixes::

        "modname"          -> required
        "modname >= 1.0"   -> required with version constraint
        "? modname"        -> optional   (skipped)
        "(?) modname"      -> optional   (skipped)
        "! modname"        -> incompatible (skipped)
    """
    names: List[str] = []
    for raw in raw_dep_strings:
        raw = raw.strip()
        if not raw:
            continue
        # Skip optional and incompatible deps
        if raw[0] in ("?", "!", "("):
            continue
        name = raw.split()[0]
        if name and name not in _NEVER_DISABLE:
            names.append(name)
    return names


def _collect_safe_set(
    desired: Set[str],
    installed_mods: Optional[Dict[str, Any]],
) -> Set[str]:
    """Return *desired* expanded with all transitive required deps present in *installed_mods*.

    Any mod in the returned set is protected from being disabled — the profile
    apply will keep it enabled even if it is not explicitly listed in the profile.
    """
    safe: Set[str] = set(desired)
    if not installed_mods:
        return safe

    queue = [m for m in desired if m in installed_mods]
    visited: Set[str] = set()

    while queue:
        mod_name = queue.pop()
        if mod_name in visited:
            continue
        visited.add(mod_name)

        mod = installed_mods.get(mod_name)
        if mod is None:
            continue

        raw_deps: List[str] = getattr(mod, "raw_data", {}).get("dependencies", [])
        for dep_name in _extract_required_dep_names(raw_deps):
            if dep_name in installed_mods and dep_name not in safe:
                safe.add(dep_name)
                queue.append(dep_name)

    return safe


def build_diff(
    profile: Profile,
    installed_zip_names: List[str],
    current_enabled: Dict[str, bool],
    installed_mods: Optional[Dict[str, Any]] = None,
) -> ProfileDiff:
    """Build an immutable diff payload to reach *profile* from current state.

    Args:
        profile: The target profile specifying desired enabled mod names.
        installed_zip_names: Mod names extracted from installed ZIP files.
        current_enabled: Map of mod_name -> currently enabled in mod-list.json.
        installed_mods: Optional map of mod_name -> Mod.  When provided the
            transitive required dependencies of all desired mods are added to the
            safe set so they are not disabled by the apply.

    Returns:
        A :class:`ProfileDiff` with explicit add/remove/enable/disable/download items.

    Notes:
        ``base`` is always excluded from download and disable actions — it has no
        ZIP in the mods folder and is always kept enabled by Factorio.
    """
    _disabled_set = set(profile.disabled_in_profile)
    # desired_enabled: mods that should be active on apply
    desired_enabled = set(profile.desired_mods) - _disabled_set - _NEVER_DISABLE
    # desired_disabled: mods in profile that the user has explicitly turned off
    desired_disabled = (set(profile.desired_mods) & _disabled_set) - _NEVER_DISABLE
    installed = set(installed_zip_names) - _NEVER_DISABLE

    # safe_set built from desired_enabled only (disabled profile mods don't protect deps)
    safe_set = _collect_safe_set(desired_enabled, installed_mods)

    currently_enabled_set = {name for name, en in current_enabled.items() if en}

    items: List[ProfileDiffItem] = []

    # --- Pass 1: activate desired_enabled mods ---
    for mod in desired_enabled:
        if mod not in installed:
            # Not installed at all — needs downloading
            items.append(ProfileDiffItem(action=DiffAction.DOWNLOAD, mod_name=mod))
        elif mod not in currently_enabled_set:
            # Installed but disabled — enable it
            items.append(ProfileDiffItem(action=DiffAction.ENABLE, mod_name=mod))
        # else already enabled — no action needed

    # --- Pass 2: deactivate desired_disabled mods that are currently enabled ---
    for mod in desired_disabled:
        if mod in installed and mod in currently_enabled_set:
            items.append(ProfileDiffItem(action=DiffAction.DISABLE, mod_name=mod))

    # --- Pass 3: disable installed mods that are not in safe_set ---
    for mod in installed:
        if mod in safe_set:
            continue  # desired or a required dep — keep it enabled
        if mod in desired_disabled:
            continue  # already handled in pass 2
        if mod in currently_enabled_set:
            # Installed and enabled but not wanted by this profile
            items.append(ProfileDiffItem(action=DiffAction.DISABLE, mod_name=mod))
        # If already disabled, no action needed

    return ProfileDiff(
        profile_id=profile.id,
        profile_name=profile.name,
        items=items,
    )


# ---------------------------------------------------------------------------
# ProfileStore
# ---------------------------------------------------------------------------


class ProfileStore:
    """Persist profiles as JSON under Config.CONFIG_DIR / "profiles"."""

    _PROFILES_FILE = "profiles.json"

    def __init__(self, profiles_dir: Optional[Path] = None) -> None:
        self._dir = profiles_dir or (Config.CONFIG_DIR / "profiles")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._profiles_file = self._dir / self._PROFILES_FILE

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def load_all(self) -> List[Profile]:
        """Return all saved profiles."""
        if not self._profiles_file.exists():
            return []
        try:
            data = json.loads(self._profiles_file.read_text(encoding="utf-8"))
            return [Profile.from_dict(p) for p in data.get("profiles", [])]
        except (json.JSONDecodeError, KeyError):
            return []

    def save(self, profile: Profile) -> None:
        """Upsert *profile* by ID."""
        if not profile.name or not profile.name.strip():
            raise ValueError("Profile name must not be empty.")
        profiles = {p.id: p for p in self.load_all()}
        profiles[profile.id] = profile
        self._write(list(profiles.values()))

    def delete(self, profile_id: str) -> None:
        """Remove profile by ID (no-op if not found)."""
        profiles = [p for p in self.load_all() if p.id != profile_id]
        self._write(profiles)

    def _write(self, profiles: List[Profile]) -> None:
        payload = json.dumps({"profiles": [p.to_dict() for p in profiles]}, indent=2)
        self._profiles_file.write_text(payload, encoding="utf-8")

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: ProfileSnapshot) -> None:
        snaps_dir = self._dir / "snapshots"
        snaps_dir.mkdir(parents=True, exist_ok=True)
        path = snaps_dir / f"{snapshot.id}.json"
        path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

    def load_snapshot(self, snapshot_id: str) -> Optional[ProfileSnapshot]:
        path = self._dir / "snapshots" / f"{snapshot_id}.json"
        if not path.exists():
            return None
        try:
            return ProfileSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError):
            return None

    def invalidate_snapshot(self, snapshot_id: str) -> None:
        snap = self.load_snapshot(snapshot_id)
        if snap:
            snap.valid = False
            self.save_snapshot(snap)
