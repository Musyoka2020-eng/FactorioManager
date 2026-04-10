# ROADMAP

## Milestone

v1.0 Ui Redesign

## Phases

- [ ] **Phase 1: Qt Platform Migration and Behavior Parity** - Move all user-facing screens to a single Qt stack while preserving existing downloader, checker, and logging behavior.
- [ ] **Phase 2: Fluent Shell and UX System** - Deliver a cohesive Fluent glassy shell, consistent navigation, and clear action feedback across core screens.
- [ ] **Phase 3: Search, Filtering, and Settings Foundation** - Add unified search/sort/filter plus centralized settings, theming, and safe credential handling.
- [ ] **Phase 4: Queue Control and Profile Workflows** - Enable robust queue execution controls and profile/preset flows with safe preview and rollback.
- [ ] **Phase 5: Dependency Intelligence and Smart Update Guidance** - Provide dependency graph visibility and explainable update risk guidance that feeds batch queue actions.
- [ ] **Phase 6: Onboarding and Contextual Help** - Add first-run guidance and replayable contextual help so users can adopt advanced workflows quickly.

## Phase Details

### Phase 1: Qt Platform Migration and Behavior Parity
**Goal**: Users interact with a fully Qt-based app without losing existing download, update-check, and logging capabilities.
**Depends on**: Nothing (first phase)
**Requirements**: PLAT-01, PLAT-02, PLAT-03
**Success Criteria** (what must be TRUE):
1. User can launch and use all primary app screens through one Qt UI path only.
2. User cannot access any legacy Tkinter production screen path.
3. User can complete download, update check, and log viewing workflows with behavior equivalent to the pre-migration app.
**Plans**: TBD
**UI hint**: yes

### Phase 2: Fluent Shell and UX System
**Goal**: Users experience a cohesive Fluent glassy interface with consistent structure and responsive interaction feedback.
**Depends on**: Phase 1
**Requirements**: UXUI-01, UXUI-02, UXUI-03
**Success Criteria** (what must be TRUE):
1. User sees a consistent Fluent glassy visual system in Main shell, Downloader, Checker, and Logs.
2. User can move between app sections using a consistent navigation and layout hierarchy.
3. User receives immediate, non-blocking feedback for high-frequency actions.
**Plans**: TBD
**UI hint**: yes

### Phase 3: Search, Filtering, and Settings Foundation
**Goal**: Users can quickly discover mods and control app configuration and appearance from one centralized settings experience.
**Depends on**: Phase 2
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SETT-01, SETT-02, SETT-03
**Success Criteria** (what must be TRUE):
1. User can run one unified search across installed, downloadable, and queued mods.
2. User can filter and sort mod lists by required states and priorities without leaving current workflow context.
3. User can manage account/token, paths, behavior, and appearance from centralized settings.
4. User can switch theme mode and bounded visual customization options and see changes reflected in the app.
5. User sees credential fields masked and validated, and credentials persist safely across sessions.
**Plans**: TBD
**UI hint**: yes

### Phase 4: Queue Control and Profile Workflows
**Goal**: Users can control execution flow safely and switch between mod-set profiles with preview and rollback confidence.
**Depends on**: Phase 3
**Requirements**: QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04, PROF-01, PROF-02, PROF-03, PROF-04
**Success Criteria** (what must be TRUE):
1. User can pause, resume, reorder, and cancel queued or running operations with clear status transitions.
2. User can recover from failed operations using actionable options such as retry, skip, or inspect.
3. User can save current mod selection as a named profile and seed profiles from starter presets.
4. User can preview the apply diff before switching profile and explicitly confirm the changes.
5. User can apply a profile and undo through a reversible snapshot.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Dependency Intelligence and Smart Update Guidance
**Goal**: Users can understand dependency impact and apply update decisions safely using explainable assistant guidance.
**Depends on**: Phase 4
**Requirements**: DEPS-01, DEPS-02, DEPS-03, UPDT-01, UPDT-02, UPDT-03
**Success Criteria** (what must be TRUE):
1. User can open a read-only dependency graph for a selected mod.
2. User can switch between simplified and full transitive graph views.
3. User can clearly identify required, optional, incompatible, and missing dependency states in the graph.
4. User can view update classifications as safe, review, or risky with rationale for each recommendation.
5. User can send assistant-recommended batch actions into queue workflow.
**Plans**: TBD
**UI hint**: yes

### Phase 6: Onboarding and Contextual Help
**Goal**: Users can get productive quickly through concise first-run guidance and replayable contextual help.
**Depends on**: Phase 5
**Requirements**: ONBD-01, ONBD-02, ONBD-03
**Success Criteria** (what must be TRUE):
1. User receives a short, skippable first-run onboarding flow focused on essential setup.
2. User sees contextual help where features are first encountered.
3. User can replay onboarding/help from settings at any time.
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Qt Platform Migration and Behavior Parity | 3/3 | Complete   | 2026-04-09 |
| 2. Fluent Shell and UX System | 0/0 | Not started | - |
| 3. Search, Filtering, and Settings Foundation | 0/0 | Not started | - |
| 4. Queue Control and Profile Workflows | 0/0 | Not started | - |
| 5. Dependency Intelligence and Smart Update Guidance | 0/0 | Not started | - |
| 6. Onboarding and Contextual Help | 0/0 | Not started | - |
