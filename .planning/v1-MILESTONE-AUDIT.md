---
milestone: v1.0
audited: 2026-04-11T00:00:00Z
status: gaps_found
scores:
  requirements: 3/33
  phases_verified: 1/7
  integration: 3/5
  flows: 4/5
gaps:
  requirements:
    - id: "PREP-01"
      status: "partial"
      phase: "Phase 0"
      claimed_by_plans: ["00-01-PLAN.md"]
      completed_by_plans: ["00-01-SUMMARY.md"]
      verification_status: "missing"
      evidence: "SUMMARY confirms selenium removed; REQUIREMENTS.md checkbox still [ ]; no Phase 0 VERIFICATION.md exists"
    - id: "PREP-02"
      status: "partial"
      phase: "Phase 0"
      claimed_by_plans: ["00-01-PLAN.md"]
      completed_by_plans: ["00-01-SUMMARY.md"]
      verification_status: "missing"
      evidence: "SUMMARY confirms credential auth removed from UI layer; core/ credential params still present (dead); no VERIFICATION.md"
    - id: "PREP-03"
      status: "partial"
      phase: "Phase 0"
      claimed_by_plans: ["00-02-PLAN.md"]
      completed_by_plans: ["00-02-SUMMARY.md"]
      verification_status: "missing"
      evidence: "SUMMARY confirms download button re-enable fixed; integration checker confirmed _on_download_finished wired; no VERIFICATION.md"
    - id: "PREP-04"
      status: "partial"
      phase: "Phase 0"
      claimed_by_plans: ["00-02-PLAN.md"]
      completed_by_plans: ["00-02-SUMMARY.md"]
      verification_status: "missing"
      evidence: "SUMMARY confirms Clear Log button wired; integration checker confirmed clear_btn.clicked.connect(clear_logs); no VERIFICATION.md"
    - id: "PREP-05"
      status: "partial"
      phase: "Phase 0"
      claimed_by_plans: ["00-03-PLAN.md"]
      completed_by_plans: ["00-03-SUMMARY.md"]
      verification_status: "missing"
      evidence: "PARITY-CHECKLIST.md confirmed at .planning/phases/00-pre-migration-cleanup/PARITY-CHECKLIST.md; no VERIFICATION.md"
    - id: "PLAT-01"
      status: "partial"
      phase: "Phase 1"
      claimed_by_plans: ["01-01-PLAN.md through 01-06-PLAN.md"]
      completed_by_plans: ["01-01-SUMMARY.md through 01-06-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Integration checker confirms all pages at page_host indices 0-3; ROADMAP shows [x]; no VERIFICATION.md"
    - id: "PLAT-02"
      status: "partial"
      phase: "Phase 1"
      claimed_by_plans: ["01-01-PLAN.md through 01-06-PLAN.md"]
      completed_by_plans: ["01-01-SUMMARY.md through 01-06-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Integration checker confirms zero tkinter imports in source tree; no VERIFICATION.md"
    - id: "PLAT-03"
      status: "partial"
      phase: "Phase 1"
      claimed_by_plans: ["01-05-PLAN.md", "01-06-PLAN.md"]
      completed_by_plans: ["01-05-SUMMARY.md", "01-06-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Integration checker confirms download, update-check, and log flows complete E2E via Qt path; no VERIFICATION.md"
    - id: "SETT-01"
      status: "unsatisfied"
      phase: "Phase 3"
      claimed_by_plans: ["03-03-PLAN.md"]
      completed_by_plans: []
      verification_status: "missing"
      evidence: "settings_page.py exists but load_values() never called on navigation to Settings page. First-visit form state is widget constructor defaults. Saving in this state silently overwrites config with garbage values."
    - id: "SETT-02"
      status: "unsatisfied"
      phase: "Phase 3"
      claimed_by_plans: ["03-03-PLAN.md", "03-05-PLAN.md"]
      completed_by_plans: []
      verification_status: "missing"
      evidence: "(1) load_values() gap means theme combo reads 'Dark' by default regardless of saved value. (2) main.py calls load_stylesheet() (always dark) not load_and_apply_theme() — saved theme never applied at startup."
    - id: "SETT-03"
      status: "unsatisfied"
      phase: "Phase 3"
      claimed_by_plans: ["03-03-PLAN.md"]
      completed_by_plans: []
      verification_status: "missing"
      evidence: "Same load_values() gap — max_workers shows spinbox minimum, auto_backup/auto_refresh unchecked on first visit regardless of config."
    - id: "SRCH-01"
      status: "partial"
      phase: "Phase 3"
      claimed_by_plans: ["03-04-PLAN.md"]
      completed_by_plans: []
      verification_status: "missing"
      evidence: "search_bar.py exists, signal wiring present; no SUMMARY or VERIFICATION for plan 03-04; plan 03-06 (human checkpoint) not done"
    - id: "SRCH-02"
      status: "partial"
      phase: "Phase 3"
      claimed_by_plans: ["03-02-PLAN.md"]
      completed_by_plans: ["03-02-SUMMARY.md"]
      verification_status: "missing"
      evidence: "FilterSortBar wired to CheckerTab; no Phase 3 VERIFICATION.md"
    - id: "SRCH-03"
      status: "partial"
      phase: "Phase 3"
      claimed_by_plans: ["03-02-PLAN.md"]
      completed_by_plans: ["03-02-SUMMARY.md"]
      verification_status: "missing"
      evidence: "CategoryChipsBar -> CategoryBrowseWorker -> portal.search_mods(category=...) wired; no Phase 3 VERIFICATION.md"
  integration:
    - "Phase 2 VERIFICATION.md truth #7 is architecturally stale — describes _stage2_widget/_stage3_widget visibility which was replaced by 03-02 browse redesign (_mod_card/_no_mod_lbl). UXUI-01/02 still satisfied; artifact is stale documentation only."
  flows:
    - "Theme switching flow: breaks before Settings page loads — load_values() never called on navigation, so controls show widget defaults not saved config. Saving destroys saved preferences."
    - "Theme persistence on restart: main.py calls load_stylesheet() (dark-only) unconditionally. Any user-saved theme preference is ignored at next app launch."
tech_debt:
  - phase: "02-fluent-shell-ux"
    items:
      - "checker_tab.py line 167: _notify helper does not expose event_key passthrough — checker toasts cannot participate in key-based dedup"
      - "main_window.py line 170: placeholder fallback labels in ImportError branches — low risk, defensive only"
      - "Phase 2 VERIFICATION.md truth #7 refers to removed code (_stage2/_stage3_widget) — update or supersede VERIFICATION.md after Phase 3 completes"
  - phase: "00-pre-migration-cleanup"
    items:
      - "core/downloader.py and core/checker.py retain dead username/token constructor params — Phase 0 credential removal only applied to UI/config layer; core constructors still accept but ignore these params"
  - phase: "03-search-filter-settings"
    items:
      - "REQUIREMENTS.md traceability table still shows Pending for PREP-01..05 and PLAT-01..03 despite work being complete — checkboxes and traceability need update"
      - "ROADMAP.md Phase 2 still marked [ ] despite VERIFICATION.md passing — progress table is stale"
      - "Plans 03-03, 03-04, 03-05 have no SUMMARY.md — execution artifacts missing despite code existing in ui dir"
nyquist:
  compliant_phases: []
  partial_phases:
    - "01-qt-platform-migration (VALIDATION.md exists, nyquist_compliant: false, wave_0_complete: false)"
    - "02-fluent-shell-ux (VALIDATION.md exists, nyquist_compliant: false, wave_0_complete: false)"
    - "03-search-filter-settings (VALIDATION.md exists, nyquist_compliant: false, wave_0_complete: false)"
  missing_phases:
    - "00-pre-migration-cleanup (no VALIDATION.md)"
  overall: "NONE — 0 phases Nyquist-compliant; 3 partial; 1 missing"
---

# Milestone v1.0 — Audit Report

**Milestone:** v1.0 UI Redesign  
**Audited:** 2026-04-11  
**Status:** `gaps_found`  
**Auditor:** gsd-audit-milestone

---

## Scores

| Area | Score | Notes |
|------|-------|-------|
| Requirements | 3/33 (9%) | Only UXUI-01/02/03 formally satisfied; 8 more functionally complete but unverified; 22 not yet started |
| Phases verified | 1/7 (14%) | Phase 2 only; Phases 0+1 complete but unverified; Phases 3-6 in progress or not started |
| Integration | 3/5 (60%) | 3 clean handoffs; 2 wiring gaps (load_values, startup theme) |
| E2E flows | 4/5 (80%) | Theme-switching flow broken; all other primary flows working |

---

## Phase Status Overview

| Phase | Plans Done | SUMMARY.md | VERIFICATION.md | Status |
|-------|-----------|------------|-----------------|--------|
| 0: Pre-Migration Cleanup | 3/3 | ✅ All 3 | ❌ None | **Unverified** (blocker) |
| 1: Qt Platform Migration | 6/6 | ✅ All 6 | ❌ None | **Unverified** (blocker) |
| 2: Fluent Shell and UX | 4/4 | ✅ All 4 | ✅ `passed` 10/10 | **Verified** |
| 3: Search/Filter/Settings | 2/6* | ⚠️ Only 03-01/02 | ❌ None | **In-Progress** |
| 4: Queue Control | 0/TBD | — | — | **Not started** |
| 5: Dependency Intelligence | 0/TBD | — | — | **Not started** |
| 6: Onboarding | 0/TBD | — | — | **Not started** |

> *Plans 03-03, 03-04, 03-05 have no SUMMARY.md despite code existing in the `ui/` directory (`settings_page.py`, `search_bar.py`, `mod_details_dialog.py`). These plans were executed without formal completion artifacts.

---

## Unsatisfied Requirements

### Critical — Phase Verification Missing

Phases 0 and 1 are marked complete in ROADMAP.md and all plan SUMMARYs exist, but neither phase has a `VERIFICATION.md`. Per audit rules, missing verification is a blocker for the 8 requirements mapped to those phases.

Integration analysis confirms functional correctness for PREP-01..05 and PLAT-01..03 — the gap is documentary, not behavioral.

| REQ-ID | Description | Functional | Blocker Reason |
|--------|-------------|------------|----------------|
| PREP-01 | Selenium dep removed | ✅ (integration confirmed) | No VERIFICATION.md for Phase 0 |
| PREP-02 | Credential auth removed | ✅ (UI/config layer only) | No VERIFICATION.md for Phase 0 |
| PREP-03 | Download button re-enables after offline fail | ✅ | No VERIFICATION.md for Phase 0 |
| PREP-04 | Clear Log button wired | ✅ | No VERIFICATION.md for Phase 0 |
| PREP-05 | Behavioral parity checklist exists | ✅ | No VERIFICATION.md for Phase 0 |
| PLAT-01 | All screens via Qt path | ✅ | No VERIFICATION.md for Phase 1 |
| PLAT-02 | No Tkinter production path | ✅ | No VERIFICATION.md for Phase 1 |
| PLAT-03 | Full E2E behavioral parity | ✅ | No VERIFICATION.md for Phase 1 |

**Recommended action:** Run `/gsd-verify-work` for Phase 0 and Phase 1 to produce VERIFICATION.md artifacts, then recheck. Given integration checker results, both phases should pass quickly.

---

### Critical — Settings Page Broken (SETT-01, SETT-02, SETT-03)

The Settings page (`settings_page.py`) was implemented but has two wiring bugs that completely break all three SETT requirements:

#### Bug 1: `load_values()` never called on navigation

`MainWindow._on_nav_changed()` switches `page_host` to index 3 (Settings) without calling `self._settings_page.load_values()` first. The Settings form opens with widget-constructor defaults:
- Theme combo: "Dark" (regardless of saved preference)
- Max workers: spinbox minimum (1)
- Auto-backup / Auto-refresh: unchecked

**Risk: Data loss** — if user clicks Save without changing anything, their saved config is silently overwritten with these defaults.

```python
# main_window.py: _on_nav_changed() currently switches page_host index only.
# Fix: add this before self.page_host.setCurrentIndex(index):
if index == 3:
    self._settings_page.load_values()
```

#### Bug 2: Startup theme always renders dark

`main.py` line 28:
```python
app.setStyleSheet(load_stylesheet())  # always dark_theme.qss
```
Should be:
```python
from factorio_mod_manager.ui.styles import load_and_apply_theme
from factorio_mod_manager.utils.config import config as _cfg
load_and_apply_theme(_cfg.get("theme", "dark"), app)
```

`load_and_apply_theme()` is already imported and used correctly in `main_window.py` for runtime theme changes — this fix just ensures startup respects the saved value.

---

### In-Progress — Phase 3 Incomplete

Plans 03-03 through 03-06 were partially executed (code exists but no SUMMARY.md artifacts). Plan 03-06 is the human verification checkpoint — it cannot pass until 03-03/04/05 are formally complete.

| Plan | Purpose | Code | SUMMARY.md |
|------|---------|------|------------|
| 03-03 | SettingsPage widget | ✅ `settings_page.py` | ❌ Missing |
| 03-04 | GlobalSearchBar + ModDetailsDialog | ✅ `search_bar.py`, `mod_details_dialog.py` | ❌ Missing |
| 03-05 | MainWindow wiring | ✅ (partial — load_values bug) | ❌ Missing |
| 03-06 | Human verification checkpoint | N/A | ❌ Not started |

---

### Not Started — Phases 4, 5, 6

Requirements QUEUE-01/02, PROF-01..05, DEPS-01..03, UPDT-01..03, ONBD-01..03 are not yet in scope. No action required for this audit.

---

## Cross-Phase Integration Findings

### Clean Handoffs

| Handoff | Status | Notes |
|---------|--------|-------|
| Phase 0 → 1 | ✅ Clean | No Tkinter residue; PARITY-CHECKLIST.md substantive (125 items) |
| Phase 1 → 2 | ✅ Clean | All objectName values in main_window.py match QSS selectors in dark_theme.qss and light_theme.qss |
| Phase 2 → 3 (layout redesign) | ✅ Clean (arch-stale doc) | Phase 3 browse layout has QSS selectors in both themes for all new components |

### Wiring Gaps

| Component | Provides | Gap | Req Affected |
|-----------|----------|-----|--------------|
| `SettingsPage.load_values()` | Populates form from saved config | Never called on Settings page navigation | SETT-01, SETT-02, SETT-03 |
| `load_and_apply_theme()` | Applies correct theme to QApplication | Not called at startup (`load_stylesheet()` used instead — always dark) | SETT-02 |

### Stale Artifact

Phase 2 `VERIFICATION.md` truth #7 states: *"Downloader presents staged two-column flow with progressive reveal"* and references `_stage2_widget/_stage3_widget` — which no longer exist after the Phase 3 (plan 03-02) browse redesign. The underlying requirements (UXUI-01/02) are still satisfied by the new layout. The VERIFICATION document should be superseded or annotated after Phase 3 completes.

---

## Requirements Coverage Matrix (3-Source Cross-Reference)

| REQ-ID | VERIFICATION.md | SUMMARY Frontmatter | REQUIREMENTS.md | Final Status |
|--------|----------------|---------------------|-----------------|--------------|
| PREP-01 | ❌ Missing | ✅ 00-01 | `[ ]` | **partial** |
| PREP-02 | ❌ Missing | ✅ 00-01 | `[ ]` | **partial** |
| PREP-03 | ❌ Missing | ✅ 00-02 | `[ ]` | **partial** |
| PREP-04 | ❌ Missing | ✅ 00-02 | `[ ]` | **partial** |
| PREP-05 | ❌ Missing | ✅ 00-03 | `[ ]` | **partial** |
| PLAT-01 | ❌ Missing | ✅ 01-05/06 | `[ ]` | **partial** |
| PLAT-02 | ❌ Missing | ✅ 01-05/06 | `[ ]` | **partial** |
| PLAT-03 | ❌ Missing | ✅ 01-05/06 | `[ ]` | **partial** |
| UXUI-01 | ✅ SATISFIED | ✅ 02-01, 02-03, 02-04 | `[x]` | **satisfied** |
| UXUI-02 | ✅ SATISFIED | ✅ 02-02, 02-03, 02-04 | `[x]` | **satisfied** |
| UXUI-03 | ✅ SATISFIED | ✅ 02-01 | `[x]` | **satisfied** |
| SRCH-01 | ❌ Missing | ❌ Not listed | `[ ]` | **partial** (code exists) |
| SRCH-02 | ❌ Missing | ✅ 03-02 (implicit) | `[ ]` | **partial** |
| SRCH-03 | ❌ Missing | ✅ 03-02 (implicit) | `[ ]` | **partial** |
| SETT-01 | ❌ Missing | ❌ Not listed | `[ ]` | **unsatisfied** (broken) |
| SETT-02 | ❌ Missing | ❌ Not listed | `[ ]` | **unsatisfied** (broken) |
| SETT-03 | ❌ Missing | ❌ Not listed | `[ ]` | **unsatisfied** (broken) |
| QUEUE-01 | — | — | `[ ]` | **not started** |
| QUEUE-02 | — | — | `[ ]` | **not started** |
| PROF-01..05 | — | — | `[ ]` | **not started** |
| DEPS-01..03 | — | — | `[ ]` | **not started** |
| UPDT-01..03 | — | — | `[ ]` | **not started** |
| ONBD-01..03 | — | — | `[ ]` | **not started** |

---

## Nyquist Compliance

| Phase | VALIDATION.md | `nyquist_compliant` | `wave_0_complete` | Status |
|-------|--------------|---------------------|-------------------|--------|
| 00-pre-migration-cleanup | ❌ None | — | — | **MISSING** |
| 01-qt-platform-migration | ✅ Exists | `false` | `false` | **PARTIAL** |
| 02-fluent-shell-ux | ✅ Exists | `false` | `false` | **PARTIAL** |
| 03-search-filter-settings | ✅ Exists | `false` | `false` | **PARTIAL** |

**Overall: NONE** — 0 phases Nyquist-compliant. All VALIDATION.md files are in `draft` status.  
Run `/gsd-validate-phase N` for each flagged phase after verification is complete.

---

## Tech Debt Register

| Phase | Item | Severity |
|-------|------|----------|
| Phase 0 | `core/downloader.py` + `core/checker.py`: dead `username`/`token` constructor params (credential removal was incomplete — UI/config layer only) | Low |
| Phase 2 | `checker_tab.py` line 167: `_notify` does not expose `event_key` passthrough — checker toasts cannot deduplicate repeated events | Warning |
| Phase 2 | `main_window.py` line 170: placeholder fallback labels in ImportError branches | Info |
| Phase 2 | VERIFICATION.md truth #7 describes removed code (`_stage2/_stage3_widget`) — stale artifact | Info |
| Phase 3 | REQUIREMENTS.md traceability: PREP-01..05 and PLAT-01..03 still show "Pending" — checkboxes need update once Phase 0/1 VERIFICATION.md complete | Low |
| Phase 3 | ROADMAP.md: Phase 2 still marked `[ ]` despite VERIFICATION.md `passed` | Info |
| Phase 3 | Plans 03-03, 03-04, 03-05 have no SUMMARY.md but all code exists — execution artifacts are missing | Medium |

---

## Summary

This is a **mid-milestone audit** of an active v1.0 development cycle. The milestone is not ready to archive; phases 3-6 are incomplete. The audit identifies the following priority actions:

### Immediate (blockers before continuing Phase 3)

1. **Fix SETT-01/02/03 wiring bugs** — `load_values()` on Settings navigate + `main.py` startup theme (2 code changes, ~5 min)
2. **Create SUMMARY.md for 03-03, 03-04, 03-05** — document what was built; these are missing execution artifacts
3. **Run Phase 0 verification** — `/gsd-verify-work` for Phase 0 (expected: fast pass)
4. **Run Phase 1 verification** — `/gsd-verify-work` for Phase 1 (expected: fast pass)

### After gap closure

5. Complete Phase 3 plans 03-06 (human checkpoint) and run `/gsd-verify-work` for Phase 3
6. Address Nyquist: run `/gsd-validate-phase` for phases 0-3
7. Update REQUIREMENTS.md checkboxes and ROADMAP.md progress table

---

_Audited: 2026-04-11_  
_Auditor: gsd-audit-milestone (orchestrator) + gsd-integration-checker_
