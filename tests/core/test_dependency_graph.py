"""TDD tests for dependency graph traversal.

Covers:
  1. DepNode state construction (INSTALLED, MISSING, OPTIONAL, INCOMPATIBLE, EXPANSION)
  2. Cycle detection via _visited set (no RecursionError)
  3. Simplified mode — direct deps only, children=[]]
"""
from __future__ import annotations

from unittest.mock import patch

from factorio_mod_manager.core.mod import Mod
from factorio_mod_manager.core.portal import FactorioPortalAPI, PortalAPIError
from factorio_mod_manager.core.dependency_graph import DepType, DepState, DepNode, build_dep_graph  # noqa: F401 — RED


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _portal_response(name: str, deps: list[str]) -> dict:
    """Return a minimal portal /full response dict."""
    return {
        "name": name,
        "title": name,
        "author": "Test",
        "releases": [
            {
                "version": "1.0.0",
                "info_json": {"dependencies": deps},
            }
        ],
    }


def _make_installed(name: str, version: str = "1.0.0", **dep_lists) -> Mod:
    """Return a minimal installed Mod with raw_data built from dep_lists."""
    # Build raw_data from dep_lists for the portal-response simulation
    raw_deps = dep_lists.get("dependencies", []) + \
               [f"? {n}" for n in dep_lists.get("optional_dependencies", [])] + \
               [f"! {n}" for n in dep_lists.get("incompatible_dependencies", [])] + \
               list(dep_lists.get("expansion_dependencies", []))
    raw = {
        "releases": [
            {"version": version, "info_json": {"dependencies": raw_deps}}
        ]
    }
    return Mod(
        name=name,
        title=name,
        version=version,
        author="Test",
        raw_data=raw,
        **dep_lists,
    )


# ---------------------------------------------------------------------------
# Test 1: DepNode state construction
# ---------------------------------------------------------------------------


class TestDepNodeStates:
    def test_required_dep_installed(self):
        """Required dep that IS installed → DepState.INSTALLED, DepType.REQUIRED."""
        dep_a = _make_installed("dep_a")
        root = _make_installed("root_mod", dependencies=["dep_a"])
        installed = {"root_mod": root, "dep_a": dep_a}

        with patch.object(FactorioPortalAPI, "get_mod") as mock_get:
            mock_get.return_value = _portal_response("dep_a", [])
            nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=False)

        dep_a_nodes = [n for n in nodes if n.name == "dep_a"]
        assert dep_a_nodes, "dep_a should appear in dependency graph"
        node = dep_a_nodes[0]
        assert node.dep_type == DepType.REQUIRED
        assert node.state == DepState.INSTALLED

    def test_required_dep_missing(self):
        """Required dep NOT installed and portal returns not_found → DepState.MISSING."""
        root = _make_installed("root_mod", dependencies=["missing_dep"])
        installed = {"root_mod": root}

        with patch.object(FactorioPortalAPI, "get_mod") as mock_get:
            mock_get.side_effect = PortalAPIError("not found", error_type="not_found")
            nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=True)

        missing_nodes = [n for n in nodes if n.name == "missing_dep"]
        assert missing_nodes, "missing_dep should appear in dependency graph"
        assert missing_nodes[0].state == DepState.MISSING

    def test_optional_dep_type(self):
        """Raw dep string '? dep_b' → DepType.OPTIONAL."""
        dep_b = _make_installed("dep_b")
        root = _make_installed("root_mod", optional_dependencies=["dep_b"])
        installed = {"root_mod": root, "dep_b": dep_b}

        nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=False)

        opt_nodes = [n for n in nodes if n.name == "dep_b"]
        assert opt_nodes, "dep_b should appear as optional dep"
        assert opt_nodes[0].dep_type == DepType.OPTIONAL

    def test_incompatible_dep_type(self):
        """Raw dep string '! dep_c' → DepType.INCOMPATIBLE."""
        root = _make_installed("root_mod", incompatible_dependencies=["dep_c"])
        installed = {"root_mod": root}

        nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=False)

        inc_nodes = [n for n in nodes if n.name == "dep_c"]
        assert inc_nodes, "dep_c should appear as incompatible dep"
        assert inc_nodes[0].dep_type == DepType.INCOMPATIBLE

    def test_expansion_dep_state(self):
        """Dep whose name is in FACTORIO_EXPANSIONS → DepType.EXPANSION, DepState.EXPANSION."""
        root = _make_installed("root_mod", dependencies=["space-age"])
        # Override raw_data so the raw dep string matches "space-age >= 1.0"
        root.raw_data = {
            "releases": [
                {"version": "1.0.0", "info_json": {"dependencies": ["space-age >= 1.0"]}}
            ]
        }
        installed = {"root_mod": root}

        nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=False)

        exp_nodes = [n for n in nodes if n.name == "space-age"]
        assert exp_nodes, "space-age expansion dep should appear"
        assert exp_nodes[0].dep_type == DepType.EXPANSION
        assert exp_nodes[0].state == DepState.EXPANSION


# ---------------------------------------------------------------------------
# Test 2: Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_cycle_stops_recursion(self):
        """Cyclic dep graph (mod_a → mod_b → mod_a) does not raise RecursionError."""
        mod_a = _make_installed("mod_a", dependencies=["mod_b"])
        mod_a.raw_data = {
            "releases": [{"version": "1.0.0", "info_json": {"dependencies": ["mod_b"]}}]
        }
        mod_b = _make_installed("mod_b", dependencies=["mod_a"])
        mod_b.raw_data = {
            "releases": [{"version": "1.0.0", "info_json": {"dependencies": ["mod_a"]}}]
        }
        installed = {"mod_a": mod_a, "mod_b": mod_b}

        # Must NOT raise RecursionError
        nodes = build_dep_graph("mod_a", installed, FactorioPortalAPI(), full=True)

        # Somewhere in the graph a CIRCULAR node for mod_a should exist
        all_nodes: list[DepNode] = []

        def collect(ns: list[DepNode]) -> None:
            for n in ns:
                all_nodes.append(n)
                collect(n.children)

        collect(nodes)

        circular = [n for n in all_nodes if n.state == DepState.CIRCULAR]
        assert circular, "A CIRCULAR DepNode should exist for the detected cycle"


# ---------------------------------------------------------------------------
# Test 3: Simplified mode
# ---------------------------------------------------------------------------


class TestSimplifiedMode:
    def test_simplified_returns_direct_deps_only(self):
        """full=False: child nodes of returned deps are always empty lists."""
        dep_b = _make_installed("dep_b", dependencies=["dep_c"])
        dep_b.raw_data = {
            "releases": [{"version": "1.0.0", "info_json": {"dependencies": ["dep_c"]}}]
        }
        dep_c = _make_installed("dep_c")
        root = _make_installed("root_mod", dependencies=["dep_b", "dep_c"])
        root.raw_data = {
            "releases": [{"version": "1.0.0", "info_json": {"dependencies": ["dep_b", "dep_c"]}}]
        }
        installed = {"root_mod": root, "dep_b": dep_b, "dep_c": dep_c}

        nodes = build_dep_graph("root_mod", installed, FactorioPortalAPI(), full=False)

        dep_b_nodes = [n for n in nodes if n.name == "dep_b"]
        assert dep_b_nodes
        assert dep_b_nodes[0].children == [], "Simplified mode: children must be empty"