# Plan 05-02 Summary — ModDetailsDialog 3-Tab Refactor

## Commit
`833b398` — feat(05-02): refactor ModDetailsDialog to 3-tab QTabWidget with DependenciesWidget and ChangelogWidget

## What was built
Rewrote `factorio_mod_manager/ui/mod_details_dialog.py` (154 → 780 lines) to implement a 3-tab modal dialog.

### New classes
- **`DepGraphWorker(QThread)`** — runs `build_dep_graph()` in background, emits `graph_ready: Signal(list[DepNode])` or `error: Signal(str)`
- **`ChangelogWorker(QThread)`** — calls `portal.get_mod_changelog()` in background, emits `changelog_ready: Signal(dict)` or `error: Signal(str)`
- **`DependenciesWidget(QWidget)`** — lazy-loading dependency tree inspector with Simplified / Full mode toggle, QSplitter + QTreeWidget (3 cols: Dependency / State / Constraint) with inline colour-coded DepState chips, right-side inspector panel
- **`ChangelogWidget(QWidget)`** — version-delta changelog scroll view; highlights entries newer than installed version; `setPlainText()` only (T-05-01 mitigation), Cascadia Code font
- **`ModDetailsDialog(QDialog)`** — 3-tab QTabWidget (Overview / Dependencies / Changelog); `initial_tab` kwarg; `installed_mods` kwarg; `setMinimumSize(860, 620)` / `resize(980, 700)`; lazy-loads Dependencies and Changelog tabs on first visit via `_on_tab_changed`

### Key implementation decisions
- `FactorioPortalAPI()` instantiated inside worker threads — never on main thread
- `setPlainText()` used exclusively in ChangelogWidget (no `setHtml` — verified with `grep -c "setHtml" … = 0`)
- `initial_tab` defaults to `"overview"` for backward compatibility with existing callers
- `QFont("Cascadia Code", 9)` for changelog entry text areas
- DepState chip colours: INSTALLED=#4ec952, MISSING=#d13438, PORTAL_ONLY=#b0b0b0, EXPANSION=#b0b0b0, CIRCULAR=#ffad00

## Verification
- Import check: `from factorio_mod_manager.ui.mod_details_dialog import ModDetailsDialog, DependenciesWidget, DepGraphWorker, ChangelogWidget, ChangelogWorker` — all 5 classes OK
- `setHtml` count: 0
- Test suite: **92 passed, 0 failed** (no regressions)

## Files modified
- `factorio_mod_manager/ui/mod_details_dialog.py` — full rewrite (+646/-20 lines)
