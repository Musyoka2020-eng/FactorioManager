"""Update risk classification for installed Factorio mods.

Public API
----------
UpdateClassification  — enum: SAFE | REVIEW | RISKY
GuidanceResult        — dataclass with classification, rationale list, delta summary
UpdateGuidanceClassifier  — static classify_mod() method
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .mod import Mod, FACTORIO_EXPANSIONS


# ---------------------------------------------------------------------------
# Enumerations & result type
# ---------------------------------------------------------------------------


class UpdateClassification(str, Enum):
    SAFE = "safe"
    REVIEW = "review"
    RISKY = "risky"


@dataclass
class GuidanceResult:
    classification: UpdateClassification
    rationale: list[str]
    dep_delta_summary: str


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[\s>=<!]")


def _extract_name(raw_dep: str) -> str:
    """Extract the mod name from a raw dep string, stripping prefix markers."""
    s = raw_dep.strip().lstrip("!?()")
    s = s.strip()
    m = _TOKEN_RE.search(s)
    if m:
        return s[: m.start()]
    return s


def _parse_classifier_deps(
    dep_strings: list[str],
) -> tuple[dict[str, str], dict[str, str], set[str], set[str]]:
    """Parse raw dep strings into four buckets.

    Returns
    -------
    (required_deps, optional_deps, incompatible_deps, expansion_deps)
    required_deps  : {name: constraint}
    optional_deps  : {name: constraint}
    incompatible_deps : {name}
    expansion_deps    : {name}
    """
    required: dict[str, str] = {}
    optional: dict[str, str] = {}
    incompatible: set[str] = set()
    expansion: set[str] = set()

    for raw in dep_strings:
        raw = raw.strip()
        if not raw:
            continue

        is_incompatible = False
        is_optional = False

        if raw.startswith("!"):
            is_incompatible = True
            raw = raw[1:].strip()
        elif raw.startswith("(?)"):
            is_optional = True
            raw = raw[3:].strip()
        elif raw.startswith("?"):
            is_optional = True
            raw = raw[1:].strip()

        # Extract name (first whitespace-delimited/operator-delimited token)
        m = _TOKEN_RE.search(raw)
        if m:
            name = raw[: m.start()].strip()
            constraint = raw[m.start():].strip()
        else:
            name = raw.strip()
            constraint = ""

        if not name or name == "base":
            continue

        # Expansion names override their dep_type bucket
        if name in FACTORIO_EXPANSIONS:
            expansion.add(name)
            continue

        if is_incompatible:
            incompatible.add(name)
        elif is_optional:
            optional[name] = constraint
        else:
            required[name] = constraint

    return required, optional, incompatible, expansion


def _get_installed_deps(
    mod: Mod,
) -> tuple[dict[str, str], dict[str, str], set[str], set[str]]:
    """Return parsed dep buckets for the currently-installed version of mod."""
    releases = mod.raw_data.get("releases", [])
    if releases:
        # Try to find the matching installed version; fall back to first release
        installed_release = next(
            (r for r in releases if r.get("version") == mod.version),
            releases[0],
        )
        dep_strings = installed_release.get("info_json", {}).get("dependencies", [])
        return _parse_classifier_deps(dep_strings)

    # Fallback: reconstruct from parsed Mod fields
    dep_strings = (
        list(mod.dependencies)
        + [f"? {n}" for n in mod.optional_dependencies]
        + [f"! {n}" for n in mod.incompatible_dependencies]
        + list(mod.expansion_dependencies)
    )
    return _parse_classifier_deps(dep_strings)


def _get_latest_deps(
    mod: Mod,
) -> Optional[tuple[dict[str, str], dict[str, str], set[str], set[str]]]:
    """Return parsed dep buckets for the latest available version, or None if unavailable."""
    releases = mod.raw_data.get("releases")
    if not releases:
        return None
    dep_strings = releases[-1].get("info_json", {}).get("dependencies", [])
    return _parse_classifier_deps(dep_strings)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class UpdateGuidanceClassifier:
    """Classify an update as SAFE, REVIEW, or RISKY based on dependency deltas."""

    @staticmethod
    def classify_mod(mod: Mod, installed_mods: dict[str, Mod]) -> GuidanceResult:
        """Return a GuidanceResult for updating *mod* to its latest_version.

        Parameters
        ----------
        mod:
            The mod being evaluated. Must have raw_data with releases for full analysis.
        installed_mods:
            Currently installed mods (name → Mod). Used to detect missing/conflict deps.
        """
        latest_parsed = _get_latest_deps(mod)
        if latest_parsed is None:
            return GuidanceResult(
                classification=UpdateClassification.REVIEW,
                rationale=["Update data not fully available — verify before applying"],
                dep_delta_summary="data unavailable",
            )

        inst_req, inst_opt, inst_inc, inst_exp = _get_installed_deps(mod)
        lat_req, lat_opt, lat_inc, lat_exp = latest_parsed

        risky_rationale: list[str] = []
        review_rationale: list[str] = []

        # ---- RISKY triggers ----

        # (a) New required dep that isn't installed
        for name in lat_req:
            if name not in inst_req and name not in installed_mods:
                risky_rationale.append(
                    f"Requires {name} which is not installed"
                )

        # (b) New incompatible dep that IS installed
        for name in lat_inc:
            if name in installed_mods:
                risky_rationale.append(
                    f"Conflicts with {name} which is currently installed"
                )

        # (c) New expansion dep (adds non-downloadable Factorio content requirement)
        for name in lat_exp:
            if name not in inst_exp:
                risky_rationale.append(
                    f"Now requires {name} (official Factorio content — not downloadable)"
                )

        # (d) Removes a previously required dep (may break dependents)
        for name in inst_req:
            if name not in lat_req and name not in lat_opt:
                risky_rationale.append(
                    f"Removes previously required {name} — verify dependent mods"
                )

        # Short-circuit: if any RISKY triggers fired, report RISKY immediately
        if risky_rationale:
            return GuidanceResult(
                classification=UpdateClassification.RISKY,
                rationale=risky_rationale,
                dep_delta_summary=_build_delta_summary(
                    inst_req, inst_opt, inst_exp, lat_req, lat_opt, lat_exp, risky=True
                ),
            )

        # ---- REVIEW triggers ----

        # (a) New optional dep added
        for name in lat_opt:
            if name not in inst_opt:
                review_rationale.append(f"Adds optional support for {name}")

        # (b) Constraint change on existing required dep
        for name in lat_req:
            if name in inst_req and inst_req[name] != lat_req[name]:
                review_rationale.append(f"Required version of {name} changes")

        # (c) Previously optional dep removed from optional list
        for name in inst_opt:
            if name not in lat_opt:
                review_rationale.append(
                    f"Previously optional {name} is no longer listed"
                )

        if review_rationale:
            return GuidanceResult(
                classification=UpdateClassification.REVIEW,
                rationale=review_rationale,
                dep_delta_summary=_build_delta_summary(
                    inst_req, inst_opt, inst_exp, lat_req, lat_opt, lat_exp, risky=False
                ),
            )

        return GuidanceResult(
            classification=UpdateClassification.SAFE,
            rationale=["No dependency changes detected"],
            dep_delta_summary="no dependency changes",
        )


# ---------------------------------------------------------------------------
# Internal summary helper
# ---------------------------------------------------------------------------


def _build_delta_summary(
    inst_req: dict,
    inst_opt: dict,
    inst_exp: set,
    lat_req: dict,
    lat_opt: dict,
    lat_exp: set,
    *,
    risky: bool,
) -> str:
    """Produce a one-line human-readable delta summary."""
    new_req = [n for n in lat_req if n not in inst_req]
    new_opt = [n for n in lat_opt if n not in inst_opt]
    new_exp = [n for n in lat_exp if n not in inst_exp]
    removed_req = [n for n in inst_req if n not in lat_req]

    parts = []
    if new_req:
        parts.append(f"adds {len(new_req)} required dep(s)")
    if new_opt:
        parts.append("adds optional branch")
    if new_exp:
        parts.append("adds expansion requirement")
    if removed_req:
        parts.append("removes required dep — verify dependents")

    if not parts:
        return "no dependency changes"
    return "; ".join(parts)