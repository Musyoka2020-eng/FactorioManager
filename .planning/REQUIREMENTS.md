# Requirements: Factorio Mod Manager

**Defined:** 2026-04-10
**Core Value:** Managing Factorio mods should feel fast, safe, and effortless, even for large mod setups.

## v1.0 Requirements

Requirements for the v1.0 UI Redesign milestone. Each maps to roadmap phases.

### Pre-Migration Preparation (Phase 0)

- [ ] **PREP-01**: Dead `selenium` dependency is removed from `pyproject.toml`
- [ ] **PREP-02**: Dead credential auth session setup is removed from `ModDownloader` and `FactorioPortalAPI`
- [ ] **PREP-03**: Download button re-enables correctly when the offline check fails, without requiring app restart
- [ ] **PREP-04**: Clear Log button is wired to the Logs tab and clears the log display
- [ ] **PREP-05**: A behavioral parity checklist documents all Tkinter-specific behaviors required of the Qt migration

### Platform Migration (Phase 1)

- [ ] **PLAT-01**: User can launch and use all primary app screens through one Qt UI path only
- [ ] **PLAT-02**: No legacy Tkinter production screen path is accessible to the user
- [ ] **PLAT-03**: User can complete download, update check, and log viewing with behavior equivalent to the pre-migration app (verified against PREP-05 checklist)

### User Interface and Experience (Phase 2)

- [ ] **UXUI-01**: User sees a consistent Fluent glassy visual system across the main shell, Downloader, Checker, and Logs
- [ ] **UXUI-02**: User can move between app sections using a consistent navigation and layout hierarchy
- [ ] **UXUI-03**: User receives immediate, non-blocking feedback for all high-frequency actions (download, scan, update)

### Search and Filtering (Phase 3)

- [ ] **SRCH-01**: User can run one unified search across installed, downloadable, and queued mods
- [ ] **SRCH-02**: User can filter and sort mod lists by status and priority without leaving their current workflow context
- [ ] **SRCH-03**: User can browse and search the Factorio portal by keyword or category from within the app

### Settings and Configuration (Phase 3)

- [ ] **SETT-01**: User can manage paths, behavior, and appearance from a centralized settings panel
- [ ] **SETT-02**: User can switch theme mode (dark / light / system) and see changes reflected immediately
- [ ] **SETT-03**: User can view and edit `max_workers`, `auto_backup`, and `auto_refresh` config keys through the settings panel

### Queue Management (Phase 4)

- [ ] **QUEUE-01**: User can pause, resume, reorder, and cancel queued or in-progress operations with clear status transitions
- [ ] **QUEUE-02**: User can recover from failed queue operations using retry, skip, or inspect actions

### Profiles and Presets (Phase 4)

- [ ] **PROF-01**: User can save the current mod selection as a named profile
- [ ] **PROF-02**: User can seed profiles from a set of curated starter presets
- [ ] **PROF-03**: User can preview the profile apply diff and confirm changes explicitly before apply
- [ ] **PROF-04**: User can apply a profile and undo via a reversible snapshot
- [ ] **PROF-05**: User can enable or disable individual mods via `mod-list.json` toggle inside the app

### Dependency Intelligence (Phase 5)

- [ ] **DEPS-01**: User can open a read-only dependency graph for a selected mod
- [ ] **DEPS-02**: User can switch between simplified and full transitive graph views
- [ ] **DEPS-03**: User can identify required, optional, incompatible, and missing dependency states in the graph

### Smart Update Guidance (Phase 5)

- [ ] **UPDT-01**: User can view update classifications as safe, review, or risky with a rationale for each recommendation
- [ ] **UPDT-02**: User can send assistant-recommended batch update actions directly into the queue workflow
- [ ] **UPDT-03**: User can view the per-mod changelog inside the mod details popup

### Onboarding and Help (Phase 6)

- [ ] **ONBD-01**: User receives a short, skippable first-run onboarding flow focused on essential setup
- [ ] **ONBD-02**: User sees contextual help tooltips and hints where features are first encountered
- [ ] **ONBD-03**: User can replay onboarding and contextual help from the settings panel at any time

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Automatic app self-update | Complex distribution concern; deferred until v1.0 ships |
| Cloud account sync | Local-first; deferred until local UX and profile model stabilize |
| Marketplace publishing workflow | No current user need; deferred to future milestone |
| Authenticated download path | All portal downloads use public endpoints; `username`/`token` are dead code — no auth UI needed until a real authenticated endpoint is targeted |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PREP-01 | Phase 0 | Pending |
| PREP-02 | Phase 0 | Pending |
| PREP-03 | Phase 0 | Pending |
| PREP-04 | Phase 0 | Pending |
| PREP-05 | Phase 0 | Pending |
| PLAT-01 | Phase 1 | Pending |
| PLAT-02 | Phase 1 | Pending |
| PLAT-03 | Phase 1 | Pending |
| UXUI-01 | Phase 2 | Pending |
| UXUI-02 | Phase 2 | Pending |
| UXUI-03 | Phase 2 | Pending |
| SRCH-01 | Phase 3 | Pending |
| SRCH-02 | Phase 3 | Pending |
| SRCH-03 | Phase 3 | Pending |
| SETT-01 | Phase 3 | Pending |
| SETT-02 | Phase 3 | Pending |
| SETT-03 | Phase 3 | Pending |
| QUEUE-01 | Phase 4 | Pending |
| QUEUE-02 | Phase 4 | Pending |
| PROF-01 | Phase 4 | Pending |
| PROF-02 | Phase 4 | Pending |
| PROF-03 | Phase 4 | Pending |
| PROF-04 | Phase 4 | Pending |
| PROF-05 | Phase 4 | Pending |
| DEPS-01 | Phase 5 | Pending |
| DEPS-02 | Phase 5 | Pending |
| DEPS-03 | Phase 5 | Pending |
| UPDT-01 | Phase 5 | Pending |
| UPDT-02 | Phase 5 | Pending |
| UPDT-03 | Phase 5 | Pending |
| ONBD-01 | Phase 6 | Pending |
| ONBD-02 | Phase 6 | Pending |
| ONBD-03 | Phase 6 | Pending |

**Coverage:**
- v1.0 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-10*
*Last updated: 2026-04-10 — initial definition from gap analysis*
