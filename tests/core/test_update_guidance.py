"""TDD tests for UpdateGuidanceClassifier.

Covers:
  1. SAFE when no dep changes between installed and latest
  2. RISKY when latest adds a missing required dep
  3. RISKY when latest lists an incompatible dep that IS installed
  4. RISKY when latest adds an expansion dep
  5. REVIEW when latest adds a new optional dep
  6. REVIEW when a dep constraint changes
  7. REVIEW (never KeyError) when raw_data is empty
  8. GuidanceResult.rationale is always a non-empty list[str]
"""
from __future__ import annotations


from factorio_mod_manager.core.mod import Mod
from factorio_mod_manager.core.update_guidance import (  # noqa: F401 — RED
    UpdateClassification,
    GuidanceResult,
    UpdateGuidanceClassifier,
)


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------


def _mod_with_raw(installed_deps: list[str], latest_deps: list[str]) -> Mod:
    """Return a Mod whose raw_data contains two releases (installed + latest)."""
    return Mod(
        name="test-mod",
        title="Test Mod",
        version="1.0.0",
        author="Test",
        latest_version="2.0.0",
        raw_data={
            "releases": [
                {"version": "1.0.0", "info_json": {"dependencies": installed_deps}},
                {"version": "2.0.0", "info_json": {"dependencies": latest_deps}},
            ]
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateGuidanceClassifier:
    def test_safe_no_dep_changes(self):
        """Same deps in installed and latest → SAFE."""
        mod = _mod_with_raw(["dep_a >= 1.0"], ["dep_a >= 1.0"])
        dep_a = Mod(name="dep_a", title="Dep A", version="1.0.0", author="Test")
        installed = {"test-mod": mod, "dep_a": dep_a}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.SAFE

    def test_risky_missing_required(self):
        """Latest adds 'new_required_dep >= 1.0' not in installed_mods → RISKY."""
        mod = _mod_with_raw([], ["new_required_dep >= 1.0"])
        installed = {"test-mod": mod}  # new_required_dep NOT installed

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.RISKY
        assert any("new_required_dep" in r for r in result.rationale)

    def test_risky_installed_incompatible(self):
        """Latest dep '! installed_mod' AND installed_mod IS installed → RISKY."""
        mod = _mod_with_raw([], ["! installed_mod"])
        installed_mod = Mod(name="installed_mod", title="Inst", version="1.0.0", author="T")
        installed = {"test-mod": mod, "installed_mod": installed_mod}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.RISKY

    def test_risky_expansion_added(self):
        """Latest deps contain 'space-age >= 1.0', installed deps do not → RISKY."""
        mod = _mod_with_raw([], ["space-age >= 1.0"])
        installed = {"test-mod": mod}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.RISKY

    def test_review_optional_dep_added(self):
        """Latest adds '(?) new_optional', installed lacks it → REVIEW."""
        mod = _mod_with_raw([], ["(?) new_optional"])
        installed = {"test-mod": mod}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.REVIEW

    def test_review_constraint_change(self):
        """Both versions require 'dep_a' but constraint tightened '>= 1.0' → '>= 2.0' → REVIEW."""
        dep_a = Mod(name="dep_a", title="Dep A", version="1.0.0", author="Test")
        mod = _mod_with_raw(["dep_a >= 1.0"], ["dep_a >= 2.0"])
        installed = {"test-mod": mod, "dep_a": dep_a}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.REVIEW

    def test_empty_raw_data_returns_review(self):
        """mod.raw_data == {} → REVIEW with 'not fully available' in rationale; no KeyError."""
        mod = Mod(name="test-mod", title="Test Mod", version="1.0.0", author="Test",
                  latest_version="2.0.0", raw_data={})
        installed = {"test-mod": mod}

        result = UpdateGuidanceClassifier.classify_mod(mod, installed)

        assert result.classification == UpdateClassification.REVIEW
        assert any("not fully available" in r for r in result.rationale)


class TestGuidanceResult:
    def test_rationale_is_nonempty_list(self):
        """Every result from classify_mod() has rationale as list[str] with at least one entry."""
        scenarios = [
            _mod_with_raw([], ["new_dep"]),
            _mod_with_raw(["dep"], ["dep"]),
            Mod(name="x", title="x", version="1.0.0", author="T",
                latest_version="2.0.0", raw_data={}),
        ]
        for mod in scenarios:
            result = UpdateGuidanceClassifier.classify_mod(mod, {"x": mod, "test-mod": mod})
            assert isinstance(result.rationale, list), "rationale must be a list"
            assert len(result.rationale) >= 1, "rationale must have at least one entry"
            assert all(isinstance(r, str) for r in result.rationale), "rationale entries must be str"