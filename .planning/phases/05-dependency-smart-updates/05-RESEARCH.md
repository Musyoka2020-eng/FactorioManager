# Phase 5: Dependency Intelligence and Smart Update Guidance — Research

**Researched:** 2026-04-11
**Domain:** PySide6 desktop graph inspection, dependency traversal, update risk classification, changelog rendering
**Confidence:** HIGH — all findings derived from direct codebase inspection plus verified PySide6 API knowledge

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use existing `ModDetailsDialog` as the primary inspection surface — no new shell page or standalone window.
- **D-02:** Graph entry points are existing mod-inspection paths only: Checker "View Details" and global search result details flow.
- **D-03:** Dependency graph is read-only.
- **D-04:** Exact graph rendering style is agent's discretion but must optimize for desktop readability inside the details popup, not a heavy standalone canvas.
- **D-05:** Default graph mode is simplified — shows the selected mod's direct dependency footprint first.
- **D-06:** Users can switch to full mode that expands the complete transitive dependency graph.
- **D-07:** Both views must clearly distinguish required, optional, incompatible, missing, and expansion/DLC dependency states.
- **D-08:** Simplified mode may visually de-emphasize optional branches, but they remain identifiable.
- **D-09:** Expansion/DLC requirements are non-downloadable — not treated as normal downloadable mods.
- **D-10:** Smart update guidance belongs in the Checker/update workflow — not a separate shell destination.
- **D-11:** `Safe` = no missing required deps, no incompatibilities, no expansion/DLC issue, no notable dep graph risk.
- **D-12:** `Review` = likely acceptable but changes direct/transitive dep footprint, affects optional branches meaningfully, or needs human review.
- **D-13:** `Risky` = incompatibilities, missing required deps, expansion/DLC issues, or high-impact dep changes that could destabilize the mod setup.
- **D-14:** Risk guidance is explainable — each recommendation must include plain-language rationale.
- **D-15:** "Queue Safe Updates" one-click action queues only `Safe` updates.
- **D-16:** Review and Risky items remain manually queueable through the existing queue workflow only.
- **D-17:** ModDetailsDialog includes a changelog view whenever changelog data is available.
- **D-18:** Changelog defaults to installed-version-to-latest delta first; older history accessible below.

### Agent's Discretion
- Exact graph widget and visualization mechanics, as long as D-01 through D-09 are preserved.
- Exact layout of smart guidance inside the Checker workflow.
- Exact changelog collapse/expand mechanics, as long as D-17 and D-18 are preserved.

### Deferred Ideas (OUT OF SCOPE)
- New shell destination for dependency viewing.
- Editable dependency management.
- Fully automatic execution of risky updates.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPS-01 | User can open a read-only dependency graph for a selected mod | Dependency Graph Approach + ModDetailsDialog Extension sections |
| DEPS-02 | User can switch between simplified and full transitive graph views | Graph Data Model section — simplified vs full rendering modes |
| DEPS-03 | User can identify required, optional, incompatible, and missing dependency states in the graph | Graph Data Model section — DepState enum + DepType enum |
| UPDT-01 | User can view update classifications as safe, review, or risky with rationale | Classifier Design section — UpdateGuidanceClassifier |
| UPDT-02 | User can send assistant-recommended batch update actions directly into the queue | Queue Integration section — SmartUpdateStrip → QueueController path |
| UPDT-03 | User can view per-mod changelog inside the mod details popup | Changelog Integration section |
</phase_requirements>

---

## Summary

**Key findings:**

- **QTreeWidget is the right graph widget.** The UI-SPEC mandates a "desktop-first hybrid tree inspector" (left pane: tree; right pane: inspector card). `QTreeWidget` with top-level group nodes (Required / Optional / Conflicts / Expansion) is the simplest correct solution — no custom `QPainter`, no external graph library, fully native PySide6. [VERIFIED: PySide6 codebase inspection]

- **Dependency data is already structured.** `Mod.dependencies`, `Mod.optional_dependencies`, `Mod.incompatible_dependencies`, `Mod.expansion_dependencies` are all already populated by `FactorioPortalAPI.get_mod_dependencies()`. The graph model needs to traverse them recursively with cycle detection, but no new parsing is needed. [VERIFIED: portal.py direct inspection]

- **Classification belongs in `core/` as a pure-Python module.** The `Safe`/`Review`/`Risky` rules (D-11 through D-13) are deterministic checks against the mod's future dep list vs the installed mods dict — no UI dependency. This mirrors the `CheckerPresenter` pattern. [VERIFIED: codebase architecture inspection]

- **Changelog scraping already works.** `portal.get_mod_changelog(mod_name)` returns `Dict[str, str]` (version → raw text) by scraping `https://mods.factorio.com/mod/{name}/changelog`. Version-keyed dict allows delta rendering (installed → latest) trivially. [VERIFIED: portal.py direct inspection]

- **`ModDetailsDialog` needs major surgery.** The current flat `QVBoxLayout` must be refactored to `QTabWidget` (Overview / Dependencies / Changelog). Header metadata stays above the tabs. Dialog minimum size must increase to 860×620 per UI-SPEC. Tabs load lazily on first activation — no blocking portal call on dialog open. [VERIFIED: mod_details_dialog.py direct inspection]

- **Queue integration is straight-line.** "Queue Safe Updates" follows the identical code path as "Update Selected": `QueueOperation(kind=UPDATE)` → `controller.enqueue()` → `controller.start_next()` → `UpdateQueueJob.start(controller)`. The only difference is the mod list is pre-filtered to Safe-only. [VERIFIED: queue_controller.py + update_queue_job.py direct inspection]

**Primary recommendation:** Add two new pure-Python modules (`core/dependency_graph.py`, `core/update_guidance.py`), extend `ModDetailsDialog` to a tabbed layout, add `SmartUpdateStrip` to `checker_tab.py` using the existing `QueueController` path. No new dependencies required.

---

## Dependency Graph Approach

### Recommended: QTreeWidget + Inspector Panel (Hybrid Tree)

**Widget:** `QTreeWidget` in a `QSplitter` (left pane) paired with a custom inspector `QWidget` (right pane), all inside a new `Dependencies` tab in `ModDetailsDialog`.

**Why `QTreeWidget` over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| `QTreeWidget` | ✅ Recommended | Built-in expand/collapse, custom item rendering, header support, sufficient for bounded tree depth (~4–6 levels). No custom delegate required for this use case. |
| `QTreeView` + custom model | ❌ Overkill | Requires `QAbstractItemModel` subclass with 100+ lines of boilerplate for a read-only display. Adds complexity with no benefit over `QTreeWidget` for static trees. |
| Custom `QPainter` canvas | ❌ Wrong scope | Canvas-style force-directed graphs require external layout engines (networkx, graphviz) and are not "desktop-first" for a bounded mod list. D-04 explicitly rules this out. |
| Third-party graph widget (e.g., `pyqtgraph`, `networkx + matplotlib`) | ❌ New dep | Adds no-value dependency. Tree topology (parent → child) is sufficient; a node-link force graph is not needed. |

**Layout inside the Dependencies tab:**
```
DependenciesTab (QWidget)
├── toolbar_row (QHBoxLayout)
│   ├── simplified_btn / full_btn (QButtonGroup, exclusive)
│   ├── legend (inline colored chips)
│   └── collapse_all_btn (hidden in Simplified mode)
└── splitter (QSplitter, Horizontal)
    ├── tree_pane (QTreeWidget, stretch 2)
    └── inspector_pane (QWidget, stretch 1, min width 240)
```

**Top-level group nodes in the tree (fixed order per UI-SPEC):**
1. Required  
2. Optional  
3. Conflicts  
4. Expansion Requirements  

Each group node is a non-selectable `QTreeWidgetItem`. Leaf nodes (individual deps) are selectable and emit a selection signal to update the right inspector pane.

**State chips on tree rows:** Use `QTreeWidgetItem.setForeground()` + `setData()` for color-coded state. Unicode glyphs (✓ Installed, ✗ Missing, ⊘ Incompatible, 🔒 Expansion) are sufficient — no icon file dependency needed. [ASSUMED: glyph availability; low risk]

**Significance:** `QTreeWidget` is already used in `CheckerTab` (the mod table inherits from `QTableWidget`), confirming the team is already comfortable with Qt item model widgets. [VERIFIED: checker_tab.py inspection]

---

## Graph Data Model

### Core Data Types (new file: `core/dependency_graph.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class DepType(str, Enum):
    REQUIRED    = "required"
    OPTIONAL    = "optional"
    INCOMPATIBLE = "incompatible"
    EXPANSION   = "expansion"

class DepState(str, Enum):
    INSTALLED   = "installed"    # in installed_mods dict
    MISSING     = "missing"      # required but not installed
    PORTAL_ONLY = "portal_only"  # not installed, but downloadable
    EXPANSION   = "expansion"    # in FACTORIO_EXPANSIONS — not downloadable
    CIRCULAR    = "circular"     # detected cycle — stop recursion here

@dataclass
class DepNode:
    name: str
    dep_type: DepType
    state: DepState
    version_constraint: str = ""   # raw constraint string, e.g., ">= 1.4"
    installed_version: Optional[str] = None
    children: list[DepNode] = field(default_factory=list)
```

### Traversal Function

```python
def build_dep_graph(
    root_name: str,
    installed_mods: dict[str, Mod],
    portal: FactorioPortalAPI,
    *,
    full: bool = False,
    _visited: set[str] | None = None,
    _depth: int = 0,
) -> list[DepNode]:
    """
    Returns a list of top-level DepNode groups (required, optional, …)
    rooted at root_name.
    """
```

**Key behavioural rules:**

| Concern | Approach |
|---------|----------|
| Cycle detection | `_visited: set[str]` threaded through all recursive calls. On cycle: append `DepNode(name=..., state=DepState.CIRCULAR)` and return without further recursion. |
| Simplified mode | Only the root mod's direct dep lists are expanded. Transitive children are added as leaf nodes with `children=[]` plus a child-count metadata hint for the inspector to display. |
| Full mode | Recurse to depth 2 for Required chains; leave Optional chains collapsed (children populated but not auto-expanded by the widget). User can manually expand deeper. |
| Missing required dep | State = `MISSING` — no recursion (cannot know that dep's deps without portal fetch). Surface as a RISKY signal to the classifier. |
| Expansion dep | State = `EXPANSION` — no recursion. Non-downloadable. |
| Incompatible dep | State depends on whether the conflicting mod is in `installed_mods`. If it IS installed: visually flagged as active incompatibility (RISKY signal). |
| Portal not available | Fall back to installed mod's `Mod.raw_data` for the root's dep list; children of transitive deps degrade to `portal_only` with no further expansion. Show the shared error state copy from copywriting contract. |

### Raw Version Constraints

`FactorioPortalAPI.get_mod_dependencies()` discards version constraint strings when building `Mod.dependencies`. The dep graph model needs the raw constraint for the inspector panel. **Option**: Call `portal.get_mod()` and parse `info_json["dependencies"]` directly in `build_dep_graph()` rather than using the pre-parsed lists. This avoids modifying the existing `Mod` dataclass. [VERIFIED: portal.py lines 130–185 — raw parsing is available]

For the root mod already in `installed_mods`, use `mod.raw_data["releases"][-1]["info_json"]["dependencies"]` to avoid a redundant API call. [VERIFIED: Mod.raw_data field + portal parse pattern]

---

## Classifier Design

### New file: `core/update_guidance.py`

**Pattern mirrors `CheckerPresenter` — pure Python, no UI imports.**

```python
class UpdateClassification(str, Enum):
    SAFE   = "safe"
    REVIEW = "review"
    RISKY  = "risky"

@dataclass
class GuidanceResult:
    classification: UpdateClassification
    rationale: list[str]           # 2-4 plain-language bullets (D-14)
    dep_delta_summary: str         # e.g., "adds optional branch", "no change"
```

### Classification Rules (D-11 / D-12 / D-13)

Derived from CONTEXT.md decisions and mapped to concrete checks against the mod's latest release dep list vs the installed mods dict:

```
classify_mod(mod: Mod, installed_mods: dict[str, Mod]) -> GuidanceResult
```

The classifier reads `mod.raw_data["releases"][-1]["info_json"]["dependencies"]` (latest version's dep list) and compares against the currently installed state.

| Tier | Trigger Condition(s) | Example Rationale |
|------|---------------------|-------------------|
| **RISKY** | Latest version has a required dep that is NOT installed | "Requires mod-name which is not installed" |
| **RISKY** | Latest version lists an incompatible dep that IS installed | "Conflicts with installed-mod which is currently installed" |
| **RISKY** | Latest version adds an expansion/DLC requirement the user may not have | "Now requires the Space Age DLC" |
| **RISKY** | Latest version drops a previously required dep (breaking contract) | [ASSUMED — treat as RISKY out of caution; confirm with user if needed] |
| **REVIEW** | Latest version adds a new optional dep not in the current dep footprint | "Adds optional support for new-mod" |
| **REVIEW** | Latest version changes an existing required dep's version constraint | "Required version of dep-mod changes from ≥1.0 to ≥2.0" |
| **REVIEW** | Latest version removes a previously optional dep | "Previously optional dep-mod is no longer listed" |
| **SAFE** | None of the above — dep footprint is equal or a strict subset, no new incompatibilities, no new missing requireds, no expansion changes | "No dependency changes detected" |

**RISKY** takes precedence over **REVIEW**. If any RISKY condition is met, the result is RISKY regardless of REVIEW conditions. Multiple RISKY conditions accumulate rationale bullets.

**Where the classifier runs:**
- Batch: a new `CheckerLogic.classify_updates(mods: dict[str, Mod]) -> dict[str, GuidanceResult]` method, called after scan/check-updates. Results cached on `CheckerTab._guidance: dict[str, GuidanceResult]`.
- Single-mod: called during `ModDetailsDialog` Dependencies tab load to show rationale in the inspector.
- Worker: `UpdateCheckWorker` or a new peer `ClassifyWorker(QThread)` in `checker_tab.py`, following the existing `QThread` worker pattern.

**Edge cases to handle:**
- `mod.raw_data` is empty (scan was offline or portal returned nothing) → return `GuidanceResult(classification=REVIEW, rationale=["Update data not fully available — verify before applying"])`
- `mod.latest_version == mod.version` → no guidance needed (not outdated)
- `mod.status == ModStatus.UNKNOWN` or `ERROR` → return `GuidanceResult(classification=REVIEW, ...)` 
- Version constraint parsing failure → demote to REVIEW, add a rationale note

---

## Changelog Integration

### Current Portal Capability [VERIFIED: portal.py lines 280–320]

`FactorioPortalAPI.get_mod_changelog(mod_name)` scrapes `https://mods.factorio.com/mod/{name}/changelog` using BeautifulSoup with the stdlib `html.parser`. It:
- Finds all `<pre class="panel-hole-combined">` elements
- Extracts version from the first line matching `Version: X.Y.Z`
- Returns `Dict[str, str]` — e.g., `{"1.2.3": "Version: 1.2.3\n  - Fixed: ...\n  - Added: ..."}` 

**Empty dict** is returned on any error (network failure, no changelog page, parser error). No exception is raised to the caller.

### Rendering Strategy

**D-18:** Default to installed→latest delta first, older history accessible below.

```
ChangelogTab (QWidget)
├── delta_header (QLabel) — "Changes since v{installed} → v{latest} ({n} entries)"
│   shown only when installed version is known
├── changelog_scroll (QScrollArea)
│   └── content_widget (QVBoxLayout)
│       ├── [delta entries: version entries from installed+1 to latest, newest first]
│       │   Each entry: version_header_lbl + QTextEdit(readOnly=True, fixed height or expandable)
│       └── [older history: remaining entries collapsed or appended below]
└── empty_state (QLabel, hidden when data exists)
```

**Version sort for delta:** Sort version keys descending using integer-tuple comparison (same as `Mod._compare_versions()`). Entries from `installed_version+1` up to `latest_version` are the delta group. Entries older than `installed_version` are the history group.

**Rendering the text blocks:** Each changelog entry is a `QTextEdit(readOnly=True)` with `setPlainText()`. Do not use HTML rendering — the portal content is pre-formatted plain text. Preserve line breaks. The `QTextEdit` can be set to a fixed height proportional to content to avoid blank space (use `document().setTextWidth() + document().size().height()` to auto-size). [ASSUMED: height auto-sizing approach — verify during implementation]

**Network call timing:** `get_mod_changelog()` must run in a `QThread` worker, NOT in dialog `__init__` or `_setup_ui()`. The Changelog tab shows a "Loading…" state on first activation, triggers the fetch, and populates on worker completion. Follow the exact `QThread` → `Signal` → `@Slot` pattern used by `ScanWorker` in `checker_tab.py`.

**Portal data source for version info:** `mod.raw_data` already contains all released versions from the `/full` portal response. The installed version is `mod.version`. The latest version is `mod.latest_version`. Both are available without an additional portal call.

---

## ModDetailsDialog Extension

### Current Structure [VERIFIED: mod_details_dialog.py direct inspection]

Currently a flat single `QVBoxLayout`:
```
QDialog
└── root (QVBoxLayout)
    ├── title_lbl (QLabel, bold)
    ├── meta_lbl (QLabel) — author · version · downloads
    ├── status_lbl (QLabel) — installed mods only
    ├── latest_lbl (QLabel) — outdated mods only
    ├── desc_edit (QTextEdit, readOnly)  ← becomes "Overview" tab content
    └── footer (QWidget)
        ├── cta_btn ("View on Portal" / "Check for Updates")
        └── close_btn
```

### Target Structure

```
QDialog (min 860×620, comfortable default 980×700 per UI-SPEC)
└── root (QVBoxLayout, contentsMargins=20,16,20,12)
    ├── [HEADER — unchanged]
    │   ├── title_lbl
    │   ├── meta_lbl
    │   ├── status_lbl (installed only)
    │   └── latest_lbl (outdated only)
    ├── tab_widget (QTabWidget, stretch=1)
    │   ├── Tab 0: "Overview" — desc_edit (existing QTextEdit)
    │   ├── Tab 1: "Dependencies" — DependenciesWidget (new)
    │   └── Tab 2: "Changelog" — ChangelogWidget (new)
    └── footer (unchanged)
```

**Key implementation notes:**

1. **Lazy tab loading:** `DependenciesWidget` and `ChangelogWidget` initialize with placeholder labels. They trigger their data-fetch workers on first `tabBarClicked` or `currentChanged` signal — not on dialog construction. Prevents unnecessary portal calls when user only wants `Overview`.

2. **Deep-link support:** Add `initial_tab: str = "overview"` to `ModDetailsDialog.__init__`. Checker guidance buttons can pass `initial_tab="dependencies"` or `initial_tab="changelog"`. After `_setup_ui()`, resolve the tab index and call `self._tab_widget.setCurrentIndex(idx)`.

3. **Data threading to sub-widgets:** `DependenciesWidget` and `ChangelogWidget` each own their own `QThread` worker (not shared). They receive the mod `name`, `version`, `installed_mods` dict, and a `FactorioPortalAPI` instance on construction. Results are delivered via `Signal`.

4. **Dialog sizing:** Current `self.setMinimumSize(520, 400)` must increase to `self.setMinimumSize(860, 620)`. Add `self.resize(980, 700)` as comfortable default.

5. **Mod data passed to sub-widgets:** `ModDetailsDialog` already stores `self._name`, `self._version`, `self._latest_version`. Add `self._mod: Mod | None` for installed mods (currently not stored but the `data` parameter has it) to pass the full dep lists and `raw_data` to the dependency widget without an extra portal call.

---

## Queue Integration

### Existing Pattern [VERIFIED: queue_controller.py, update_queue_job.py, checker_tab.py inspection]

"Update Selected" path today:
```python
op = QueueOperation(
    source=OperationSource.CHECKER,
    kind=OperationKind.UPDATE,
    label=f"Update {len(mod_names)} mod(s)",
    continue_on_failure=True,
)
self._queue_controller.enqueue(op)
self._queue_controller.start_next()
job = UpdateQueueJob(op, mod_names, self._logic)
self._active_jobs[op.id] = job
job.start(self._queue_controller)
```

### "Queue Safe Updates" Path

Identical to the above. The only difference is that `mod_names` is pre-filtered to the Safe-only subset:

```python
def _on_queue_safe_updates(self) -> None:
    safe_names = [
        name for name, result in self._guidance.items()
        if result.classification == UpdateClassification.SAFE
        and name in self._current_scope  # respects SmartUpdateStrip scope rule
    ]
    if not safe_names:
        return  # CTA should already be disabled; guard anyway
    op = QueueOperation(
        source=OperationSource.CHECKER,
        kind=OperationKind.UPDATE,
        label=f"Queue Safe Updates ({len(safe_names)} mods)",
        continue_on_failure=True,
    )
    self._queue_controller.enqueue(op)
    self._queue_controller.start_next()
    job = UpdateQueueJob(op, safe_names, self._logic)
    self._active_jobs[op.id] = job
    job.start(self._queue_controller)
```

`OperationKind.UPDATE` is already the correct kind. No new `OperationKind` value is needed.

### Manual Queue Confirmation (Review + Risky items)

"Update Selected" with mixed or non-Safe selection shows a lightweight confirmation dialog before enqueuing. Implementation: a simple `QDialog` subclass (or `QMessageBox` with custom text) that lists Safe/Review/Risky counts and has "Queue Selected" / "View Details" / "Return to Checker" buttons. This is a new small widget class, not a full new tab.

---

## Testing Strategy

### What can be unit tested (pure Python, no Qt) [VERIFIED: existing test patterns]

| Target | Test File | Test Approach |
|--------|-----------|---------------|
| `DepType`, `DepState`, `DepNode` data types | `tests/core/test_dependency_graph.py` | Construct directly, assert fields |
| `build_dep_graph()` — simple case | same | Mock `FactorioPortalAPI.get_mod()` → return controlled dict; assert tree structure |
| `build_dep_graph()` — cycle detection | same | Mock A→B→A; assert cycle node is added, no infinite recursion |
| `build_dep_graph()` — expansion deps treated as non-downloadable | same | Mock dep with `space-age`; assert `DepState.EXPANSION` |
| `build_dep_graph()` — missing required dep | same | Mock dep not in installed_mods and portal returns 404; assert `DepState.MISSING` |
| `UpdateGuidanceClassifier.classify_mod()` — SAFE | `tests/core/test_update_guidance.py` | Mod with `raw_data` for latest version, matching installed; expect SAFE |
| Classifier — RISKY (missing required dep) | same | Latest version adds new required dep absent from installed_mods |
| Classifier — RISKY (incompatible installed mod) | same | Latest version has `!installed_mod` in deps and that mod is in installed_mods |
| Classifier — RISKY (expansion added) | same | Latest version adds `space-age` to expansion_dependencies |
| Classifier — REVIEW (optional dep added) | same | Latest version adds a new optional dep |
| Classifier — REVIEW (version constraint change) | same | Required dep's constraint tightens |
| Classifier — empty raw_data fallback | same | `mod.raw_data = {}` → returns REVIEW with "data unavailable" rationale |

### What requires manual / UI testing

| Scenario | Method |
|----------|--------|
| `QTreeWidget` tree renders correctly with correct color chips | Run app, open "View Details", click "Dependencies" tab |
| Simplified vs Full mode toggle works | Manual — click toggle, verify tree expansion changes |
| Changelog delta section shows correct version range | Manual — inspect outdated mod with known version |
| SmartUpdateStrip scope rule (selection vs no-selection) | Manual — select rows, verify strip count changes |
| Queue Safe Updates creates visible queue entry | Manual — verify queue strip + drawer show the new op |
| Confirmation sheet appears for Review/Risky Update Selected | Manual — select Review/Risky rows, click Update Selected |
| Deep-link to Dependencies tab from Checker guidance panel | Manual — click "View Details" in right sidebar |

### Fixtures needed

```python
# tests/core/test_dependency_graph.py

def _portal_response(name: str, deps: list[str]) -> dict:
    """Minimal portal /full response with dependency entries."""
    return {
        "name": name,
        "title": name,
        "author": "Test",
        "releases": [{"version": "1.0.0", "info_json": {"dependencies": deps}}],
    }

def _make_installed(name: str, version: str = "1.0.0", **dep_lists) -> Mod:
    return Mod(name=name, title=name, version=version, author="Test", **dep_lists)
```

```python
# tests/core/test_update_guidance.py

def _mod_with_latest_deps(installed_deps: list[str], latest_deps: list[str]) -> Mod:
    """Mod whose installed version has installed_deps,
    and whose raw_data simulates latest version having latest_deps."""
    return Mod(
        name="test-mod", title="Test Mod", version="1.0.0", author="Test",
        latest_version="2.0.0",
        raw_data={
            "releases": [
                {"version": "1.0.0", "info_json": {"dependencies": installed_deps}},
                {"version": "2.0.0", "info_json": {"dependencies": latest_deps}},
            ]
        },
    )
```

---

## Key Risks

### Risk 1: Portal fetch latency inside ModDetailsDialog opens a blocking-UX gap

**The problem:** `build_dep_graph()` for Full mode may need multiple sequential `portal.get_mod()` calls (one per transitive dep). Each call is 10 s timeout. For a mod with 6 transitive deps, that's up to 60 s of network I/O.

**Mitigation:** Always run dep graph construction in a `QThread` worker. Show a visible "Loading…" spinner in the Dependencies tab. Add a hard limit: for Full mode, cap transitive resolution at `depth=2` and mark deeper nodes as "expandable on demand" rather than pre-resolving everything. [ASSUMED: depth=2 is safe; may need tuning]

**Plan impact:** Every tab in `ModDetailsDialog` that fetches from portal needs its own worker setup. The planner must include this in the task for each tab widget.

### Risk 2: `Mod.raw_data` is empty for scans run without network

**The problem:** When the user runs scan without internet, `mod.raw_data = {}` (the portal call returns None and raw_data defaults to `{}`). The classifier and dep graph model both depend on `raw_data["releases"][-1]["info_json"]["dependencies"]`.

**Mitigation:** Both `build_dep_graph()` and `UpdateGuidanceClassifier.classify_mod()` must check for empty `raw_data` and handle gracefully — fall back to the local `Mod.dependencies` list for the root mod's known dep state, and return `REVIEW` classification with a "data not fully available" rationale bullet. This is explicitly modeled in the classifier edge cases section above.

**Plan impact:** All paths that use `raw_data` need a guard. Tests must cover the empty case.

### Risk 3: ModDetailsDialog refactor breaks existing callers

**The problem:** `ModDetailsDialog` is created from at least two places: `checker_tab.py::_on_view_details()` and `search_bar.py` (global search results). Any API change to `ModDetailsDialog.__init__` must remain backward-compatible or both callers must be updated together.

**Mitigation:** Keep the existing `(data, source, parent)` signature. Add only `initial_tab: str = "overview"` as an optional keyword argument — existing callers need no change. The refactor from flat layout to `QTabWidget` is internal. The existing `_status`, `_title`, `_description` etc. attributes on the dialog remain intact; the Description area simply moves into the Overview tab.

**Plan impact:** The implementer must update `search_bar.py` caller if it passes keyword arguments, and add the `initial_tab` parameter to `checker_tab.py::_on_view_details()` for the depth-link flow.

---

## Validation Architecture

### Test Framework [VERIFIED: pyproject.toml]
| Property | Value |
|----------|-------|
| Framework | pytest ^7.4.0 |
| Config file | none — pyproject.toml has no [tool.pytest] section; pytest finds tests/ by convention |
| Quick run command | `pytest tests/core/test_dependency_graph.py tests/core/test_update_guidance.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPS-01 | Dep graph opens for a selected mod | manual | — | ❌ |
| DEPS-02 | Simplified/Full toggle changes tree depth | manual | — | ❌ |
| DEPS-03 | Required/Optional/Incompatible/Missing states shown | unit + manual | `pytest tests/core/test_dependency_graph.py -x` | ❌ Wave 0 |
| UPDT-01 | Classifications Safe/Review/Risky with rationale | unit | `pytest tests/core/test_update_guidance.py -x` | ❌ Wave 0 |
| UPDT-02 | Safe updates enter queue | manual | — | ❌ |
| UPDT-03 | Changelog renders in dialog | manual | — | ❌ |

### Sampling Rate
- **Per task commit:** `pytest tests/core/ -x` (fast, no Qt required)
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green + manual verification of all 6 success criteria

### Wave 0 Gaps (test files to create before implementing)

- [ ] `tests/core/test_dependency_graph.py` — covers DEPS-03 traversal and DepState logic
- [ ] `tests/core/test_update_guidance.py` — covers UPDT-01 all three tiers + edge cases
- [ ] No new pytest fixtures or conftest.py changes needed — existing `tmp_path` and `unittest.mock.patch` patterns are sufficient for core tests

---

## dont_hand_roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency tree display | Custom `QPainter` graph canvas | `QTreeWidget` with `QTreeWidgetItem` | Built-in expand/collapse, selection, color; adequate for bounded tree depth |
| Changelog HTML parsing | Custom regex HTML scraper | BeautifulSoup (already in stack) + existing `portal.get_mod_changelog()` | Already implemented in `portal.py`; returns clean `Dict[str, str]` |
| Version comparison for changelog delta | Custom version sorting | `Mod._compare_versions()` / integer tuple comparison (already in `mod.py`) | Already implemented and tested via `update_status()` |
| Transitive dep cycle prevention | Custom graph visited tracking | `visited: set[str]` pattern (already used in `ModDownloader.resolve_dependencies()`) | Same recursive visited-set pattern works; no external graph library needed |
| Worker thread for portal fetch | Direct call from Qt slot | `QThread` subclass pattern (already used by `ScanWorker`, `UpdateCheckWorker`, etc.) | Existing convention in `checker_tab.py`; do not block event loop |
| Queue enqueue for Safe updates | New queue operation type | `OperationKind.UPDATE` (already exists) | `QueueOperation(kind=OperationKind.UPDATE)` is correct — same type used by existing Update Selected |

---

## common_pitfalls

### Pitfall 1: Calling portal.get_mod() inside `_setup_ui()` or `__init__`

**What goes wrong:** The dialog freezes during open. Qt event loop is blocked for the full 10 s timeout per dep.
**Why it happens:** `get_mod()` is a synchronous blocking HTTP call. Any code path inside `__init__` runs on the main thread.
**How to avoid:** Always defer portal calls to a `QThread` worker. Trigger the worker on `tabBarClicked(index)` for the first activation of Dependencies and Changelog tabs.
**Warning signs:** Any `portal.get_mod()` or `portal.get_mod_changelog()` call that is not inside a `QThread.run()` method.

### Pitfall 2: Sharing `_visited` set across unrelated graph builds

**What goes wrong:** Building the dep graph for mod A contaminates the `_visited` set for mod B if `_visited` is a class attribute or module-level global.
**Why it happens:** A mutable default argument or class-level set is shared across calls.
**How to avoid:** `_visited` must be created fresh as `set()` at the top of each top-level `build_dep_graph()` call and passed by reference through recursion only.

### Pitfall 3: Assuming `Mod.dependencies` contains the *latest* version's dep list

**What goes wrong:** Classifier compares the installed version's deps against the installed mods dict and reports SAFE when the latest version would actually introduce new conflicts.
**Why it happens:** `Mod.dependencies` is populated from `info_json` of the *latest* portal release — actually this is correct as long as scan was done with network. BUT if scan was done offline, `raw_data` is empty and `Mod.dependencies` may be stale from the local `info.json` inside the installed ZIP.
**How to avoid:** Classifier must read from `mod.raw_data["releases"][-1]["info_json"]["dependencies"]` when available. Fall back to `mod.dependencies` only if `raw_data` is empty, and in that case return REVIEW (not SAFE) to be conservative.

### Pitfall 4: `QTreeWidget.itemSelectionChanged` firing on programmatic tree population

**What goes wrong:** When the worker populates the tree widget, `itemSelectionChanged` fires for each item added, causing the inspector pane to update repeatedly and potentially triggering additional portal calls.
**Why it happens:** Programmatic `addTopLevelItem()` / `addChild()` can fire selection signals.
**How to avoid:** Block signals during tree construction with `self._tree.blockSignals(True)` before populating, `blockSignals(False)` after, then explicitly clear and set selection to the root mod.

### Pitfall 5: Mutating `_guidance` dict from a `ClassifyWorker` thread

**What goes wrong:** `CheckerTab._guidance` is read by the main thread for rendering. Writing to it from a worker thread creates a data race.
**Why it happens:** Python `dict` is not thread-safe for concurrent read/write.
**How to avoid:** Follow the existing `QThread` → `Signal` → `@Slot` pattern. The worker emits `guidance_ready = Signal(dict)` with a fresh dict. The `@Slot` handler on the main thread replaces `self._guidance` atomically.

### Pitfall 6: `get_mod_changelog()` printing errors to stdout instead of raising

**What goes wrong:** Changelog errors are silently swallowed by the `except Exception as e: print(...)` inside `portal.py`, and the empty `{}` return is never surfaced to the user.
**Why it happens:** Portal changelog method has a bare catch-and-print pattern (existing code).
**How to avoid:** The `ChangelogWidget` must check `if not changelog_data:` after the worker completes and show the changelog empty state (per copywriting contract) rather than leaving the tab blank.

---

## Sources

### Primary (HIGH confidence — from direct codebase inspection)
- `factorio_mod_manager/core/mod.py` — `Mod` dataclass, `FACTORIO_EXPANSIONS`, dep field names
- `factorio_mod_manager/core/portal.py` — `get_mod_dependencies()` parsing logic, `get_mod_changelog()` implementation
- `factorio_mod_manager/ui/mod_details_dialog.py` — current dialog structure to be extended
- `factorio_mod_manager/ui/checker_tab.py` — existing `QThread` worker patterns, `QueueController` integration
- `factorio_mod_manager/ui/queue_controller.py` — `enqueue()`, `start_next()` API
- `factorio_mod_manager/ui/update_queue_job.py` — job lifecycle, cancel, failure patterns
- `factorio_mod_manager/core/queue_models.py` — `OperationKind.UPDATE`, `QueueOperation`, `QueueFailure`
- `.planning/phases/05-dependency-smart-updates/05-CONTEXT.md` — locked decisions D-01 through D-18
- `.planning/phases/05-dependency-smart-updates/05-UI-SPEC.md` — visual contract, widget names, copy strings

### Secondary (MEDIUM confidence)
- `.planning/codebase/ARCHITECTURE.md` — threading model, layer boundaries, `CheckerPresenter` pattern
- `.planning/codebase/CONVENTIONS.md` — naming patterns, thread-safety rules, logging channels
- `tests/core/test_checker_mod_state.py`, `tests/ui/test_queue_controller.py` — test fixture patterns

---

## Metadata

**Confidence breakdown:**
- Dependency graph widget approach: HIGH — cross-verified against codebase, UI-SPEC, and PySide6 widget capabilities
- Graph data model: HIGH — directly extends existing dep parsing code in portal.py
- Classifier design: HIGH — rules directly derived from CONTEXT.md locked decisions D-11/D-12/D-13
- Changelog: HIGH — existing `get_mod_changelog()` is fully implemented and verified
- ModDetailsDialog extension: HIGH — current structure fully read; extension pattern is additive
- Queue integration: HIGH — "Update Selected" path is fully verified and the new path is identical with a pre-filter

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (PySide6 widget API is stable; portal scraping selector may drift if mods.factorio.com HTML changes)
