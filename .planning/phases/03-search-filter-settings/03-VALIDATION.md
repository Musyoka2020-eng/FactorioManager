---
phase: 03
slug: search-filter-settings
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SETT-02 | T-03-01 | Credential keys absent from config after removal | unit | `python -c "from factorio_mod_manager.utils.config import Config; c=Config(); assert 'username' not in c.DEFAULTS, 'credential still in DEFAULTS'"` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | SETT-01 | T-03-02 | portal.py: no auth params accepted | unit | `python -c "import inspect; from factorio_mod_manager.core.portal import FactorioPortalAPI; sig=inspect.signature(FactorioPortalAPI.__init__); assert 'username' not in sig.parameters"` | ✅ | ⬜ pending |
| 03-01-03 | 01 | 1 | SETT-02 | T-03-03 | light_theme.qss parsable with LIGHT_* token substitution | unit | `python -c "from factorio_mod_manager.ui.styles import load_and_apply_theme; print('load_and_apply_theme import OK')"` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | SRCH-02 | — | FilterSortBar emits changed signal on status change | manual | N/A — Qt widget event tested in verification checkpoint | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | SRCH-03 | — | CategoryChipsBar deselects all when same chip re-clicked | manual | N/A — Qt widget event tested in verification checkpoint | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | SETT-01 | T-03-07 | SettingsPage.has_unsaved_changes() returns True after form edit | unit | `python -m py_compile factorio_mod_manager/ui/settings_page.py && echo OK` | ✅ | ⬜ pending |
| 03-03-02 | 03 | 2 | SETT-03 | T-03-08 | _on_save writes all config keys via Config.set() | unit | `python -m py_compile factorio_mod_manager/ui/settings_page.py && echo OK` | ✅ | ⬜ pending |
| 03-04-01 | 04 | 2 | SRCH-01 | T-03-10 | All portal text displayed with PlainText format | unit | `python -c "from factorio_mod_manager.ui.mod_details_dialog import ModDetailsDialog; print('import OK')"` | ✅ | ⬜ pending |
| 03-04-02 | 04 | 2 | SRCH-01 | T-03-12 | PortalSearchWorker cancels prior run before new search | unit | `python -c "from factorio_mod_manager.ui.search_bar import GlobalSearchBar, SearchResultsPopup; print('import OK')"` | ✅ | ⬜ pending |
| 03-05-01 | 05 | 3 | SETT-01 | T-03-13 | main_window.py syntax passes py_compile | unit | `python -m py_compile factorio_mod_manager/ui/main_window.py && echo OK` | ✅ | ⬜ pending |
| 03-05-02 | 05 | 3 | SRCH-01 | — | MainWindow imports all Phase 3 widgets without error | unit | `python -c "from factorio_mod_manager.ui.main_window import FactorioModManager; print('import OK')"` | ✅ | ⬜ pending |
| 03-06-01 | 06 | 4 | SRCH-01,SRCH-02,SRCH-03,SETT-01,SETT-02,SETT-03 | — | All 6 requirements pass human visual verification | manual | Human checkpoint (see 03-06-PLAN.md) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/ui/test_filter_sort_bar.py` — stub tests for FilterSortBar signal emission (03-02-01)
- [ ] `tests/ui/test_category_chips_bar.py` — stub tests for CategoryChipsBar toggle behavior (03-02-02)

*All other tasks use py_compile or import checks on files the executor creates — no pre-creation required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FilterSortBar filter buttons update CheckerTab table | SRCH-02 | Qt widget state requires running event loop | Launch app → Checker tab → click "Outdated" filter → verify table updates |
| CategoryChipsBar sends category to portal API and updates results | SRCH-03 | Requires network + running Qt app | Launch app → Downloader tab → click "Logistics" chip → verify results change |
| SettingsPage nav-away unsaved guard prompts QMessageBox | SETT-01 | Modal dialog requires running event loop | Launch app → Settings tab → change theme → click Checker in nav → confirm dialog appears |
| Theme changes apply live on Save | SETT-02 | Visual rendering verification | Launch app → Settings → change to Light → Save → confirm stylesheet applied |
| System theme tracks OS change | SETT-02 | Requires OS-level light/dark toggle | Settings → System → Save → change OS theme → confirm app updates without restart |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
