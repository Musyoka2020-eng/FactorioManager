---
plan: 05-01
phase: 05-dependency-smart-updates
status: completed
completed: 2026-04-11
---

# Plan 05-01 Summary: Core TDD Modules

## What Was Built

Two pure-Python core modules with full unit test coverage (TDD):

### `factorio_mod_manager/core/dependency_graph.py`
- `DepType` enum: REQUIRED / OPTIONAL / INCOMPATIBLE / EXPANSION
- `DepState` enum: INSTALLED / MISSING / PORTAL_ONLY / EXPANSION / CIRCULAR
- `DepNode` dataclass with children list for recursive tree representation
- `build_dep_graph()` — recursive builder with cycle detection (`_visited` set) and depth cap (≤2 for full mode)
- `_parse_raw_dep()` — handles all Factorio dep string formats including `!`, `?`, `(?)`, and expansion override
- `_get_dep_strings()` — retrieves from mod's raw_data releases or reconstructed fields, falls back to portal

### `factorio_mod_manager/core/update_guidance.py`
- `UpdateClassification` enum: SAFE / REVIEW / RISKY
- `GuidanceResult` dataclass with classification, rationale list, dep_delta_summary
- `UpdateGuidanceClassifier.classify_mod()` — detects RISKY (missing required deps, installed incompatible conflicts, new expansion requirements, removed required deps) and REVIEW (new optional deps, constraint changes, optional dep removals)
- Safe guard: empty `raw_data` returns REVIEW with "not fully available" rationale

### `factorio_mod_manager/core/__init__.py`
- Added exports for all 7 new symbols: `DepType`, `DepState`, `DepNode`, `build_dep_graph`, `UpdateClassification`, `GuidanceResult`, `UpdateGuidanceClassifier`

## Test Results
- 15 new tests (7 dependency graph + 8 update guidance) — all pass
- Full suite: **92 passed, 0 failed**
- RED→GREEN→commit cycle followed for both modules

## Key Implementation Notes
- Cycle detection: both installed AND not-installed nodes check `_visited` before recursing (fix applied after initial RED→FAIL)
- No PySide6 imports in either core module
- `PortalAPIError` imported at runtime (not under `TYPE_CHECKING`) for except clauses

## key-files
created:
  - factorio_mod_manager/core/dependency_graph.py
  - factorio_mod_manager/core/update_guidance.py
  - tests/core/test_dependency_graph.py
  - tests/core/test_update_guidance.py
modified:
  - factorio_mod_manager/core/__init__.py
