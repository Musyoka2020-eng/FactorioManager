"""Read-only dependency graph model for Factorio mods.

Public API
----------
DepType   — enum: REQUIRED | OPTIONAL | INCOMPATIBLE | EXPANSION
DepState  — enum: INSTALLED | MISSING | PORTAL_ONLY | EXPANSION | CIRCULAR
DepNode   — dataclass holding one dependency edge
build_dep_graph()  — recursive graph builder (cycle-safe, depth-capped)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from .mod import Mod, FACTORIO_EXPANSIONS
from .portal import PortalAPIError  # runtime import for except clauses

if TYPE_CHECKING:
    from .portal import FactorioPortalAPI  # type annotation only


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DepType(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    INCOMPATIBLE = "incompatible"
    EXPANSION = "expansion"


class DepState(str, Enum):
    INSTALLED = "installed"
    MISSING = "missing"
    PORTAL_ONLY = "portal_only"
    EXPANSION = "expansion"
    CIRCULAR = "circular"


# ---------------------------------------------------------------------------
# DepNode dataclass
# ---------------------------------------------------------------------------


@dataclass
class DepNode:
    name: str
    dep_type: DepType
    state: DepState
    version_constraint: str = ""
    installed_version: Optional[str] = None
    children: list[DepNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_raw_dep(raw: str) -> tuple[str, DepType, str]:
    """Parse a raw Factorio dep string into (name, DepType, version_constraint).

    Raw dep string formats:
        "dep_name"
        "dep_name >= 1.0"
        "? dep_name"
        "? dep_name >= 1.0"
        "(?) dep_name >= 1.0"
        "! dep_name"

    Returns ("", DepType.REQUIRED, "") for empty/skip strings.
    """
    raw = raw.strip()
    if not raw:
        return ("", DepType.REQUIRED, "")

    dep_type = DepType.REQUIRED

    # Strip prefix markers
    if raw.startswith("!"):
        dep_type = DepType.INCOMPATIBLE
        raw = raw[1:].strip()
    elif raw.startswith("(?)"):
        dep_type = DepType.OPTIONAL
        raw = raw[3:].strip()
    elif raw.startswith("?"):
        dep_type = DepType.OPTIONAL
        raw = raw[1:].strip()

    # Split name from version constraint
    # Name is the first token; everything after is the version constraint
    parts = raw.split(None, 1)  # split on first whitespace
    if not parts:
        return ("", DepType.REQUIRED, "")

    name = parts[0]
    # Further strip in case name still has version characters attached
    # (shouldn't happen with proper raw strings but guard defensively)
    for sep in (">=", "<=", ">", "<", "=", "!="):
        if sep in name:
            idx = name.index(sep)
            constraint_prefix = name[idx:]
            name = name[:idx].strip()
            extra = parts[1] if len(parts) > 1 else ""
            version_constraint = (constraint_prefix + " " + extra).strip()
            break
    else:
        version_constraint = parts[1].strip() if len(parts) > 1 else ""

    if not name or name == "base":
        return ("", DepType.REQUIRED, "")

    # Override to EXPANSION if name is a known Factorio expansion
    if dep_type == DepType.REQUIRED and name in FACTORIO_EXPANSIONS:
        dep_type = DepType.EXPANSION

    return (name, dep_type, version_constraint)


def _get_dep_strings(
    root_name: str,
    installed_mods: dict[str, Mod],
    portal: "FactorioPortalAPI",
) -> list[str]:
    """Return raw dep strings for root_name from installed_mods or the portal."""
    if root_name in installed_mods:
        mod = installed_mods[root_name]
        releases = mod.raw_data.get("releases")
        if releases:
            return releases[-1].get("info_json", {}).get("dependencies", [])
        # Fallback: reconstruct from parsed fields
        dep_strings: list[str] = []
        dep_strings.extend(mod.dependencies)
        dep_strings.extend(f"? {n}" for n in mod.optional_dependencies)
        dep_strings.extend(f"! {n}" for n in mod.incompatible_dependencies)
        dep_strings.extend(mod.expansion_dependencies)
        return dep_strings

    # Not installed — fetch from portal
    try:
        data = portal.get_mod(root_name)
        if data:
            releases = data.get("releases", [])
            if releases:
                return releases[-1].get("info_json", {}).get("dependencies", [])
    except PortalAPIError:
        pass
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dep_graph(
    root_name: str,
    installed_mods: dict[str, Mod],
    portal: "FactorioPortalAPI",
    *,
    full: bool = False,
    _visited: set[str] | None = None,
    _depth: int = 0,
) -> list[DepNode]:
    """Build a flat list of DepNode for all dependencies of root_name.

    Parameters
    ----------
    root_name:
        The mod whose dependencies we inspect.
    installed_mods:
        Currently installed mods (name → Mod).
    portal:
        Portal API instance used to look up non-installed mods.
    full:
        If False (default), return only direct deps with empty children.
        If True, recurse up to depth 2 for installed required deps.
    _visited:
        Internal set used for cycle detection (passed by reference).
    _depth:
        Internal recursion depth counter.
    """
    if _visited is None:
        _visited = set()

    # Mark root as visited BEFORE processing its children (cycle detection)
    _visited.add(root_name)

    raw_strings = _get_dep_strings(root_name, installed_mods, portal)
    nodes: list[DepNode] = []

    for raw in raw_strings:
        name, dep_type, version_constraint = _parse_raw_dep(raw)
        if not name or name == "base":
            continue

        installed_version = installed_mods[name].version if name in installed_mods else None

        # Determine state
        if dep_type == DepType.EXPANSION:
            state = DepState.EXPANSION
            children: list[DepNode] = []

        elif dep_type == DepType.INCOMPATIBLE:
            # INSTALLED means the incompatible mod IS present (a conflict exists)
            state = DepState.INSTALLED if name in installed_mods else DepState.PORTAL_ONLY
            children = []

        elif name in installed_mods:
            # Cycle detection: if we've already started processing this node upstream,
            # mark it CIRCULAR rather than recursing into it again.
            if full and name in _visited:
                state = DepState.CIRCULAR
                children = []
            else:
                state = DepState.INSTALLED
                # Recurse only for required deps in full mode, within depth cap
                if (
                    full
                    and dep_type == DepType.REQUIRED
                    and _depth < 2
                ):
                    children = build_dep_graph(
                        name,
                        installed_mods,
                        portal,
                        full=True,
                        _visited=_visited,
                        _depth=_depth + 1,
                    )
                else:
                    children = []

        else:
            # Not installed
            if not full:
                state = DepState.PORTAL_ONLY
                children = []
            elif name in _visited:
                state = DepState.CIRCULAR
                children = []
            elif _depth >= 2:
                state = DepState.PORTAL_ONLY
                children = []
            else:
                # Try portal to confirm existence
                try:
                    portal.get_mod(name)
                    state = DepState.PORTAL_ONLY
                    children = []
                except PortalAPIError as exc:
                    if exc.error_type == "not_found":
                        state = DepState.MISSING
                    else:
                        state = DepState.PORTAL_ONLY
                    children = []

        node = DepNode(
            name=name,
            dep_type=dep_type,
            state=state,
            version_constraint=version_constraint,
            installed_version=installed_version,
            children=children,
        )
        nodes.append(node)

    return nodes
