# Phase 2: Fluent Shell and UX System - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a cohesive Fluent glassy interaction system across the main shell and core screens (Downloader, Checker, Logs), with consistent navigation hierarchy and immediate non-blocking action feedback.

This phase clarifies how the shell and high-frequency workflows should feel and behave. It does not add new backend capabilities.

</domain>

<decisions>
## Implementation Decisions

### Fluent Visual Language
- **D-01:** Default surface style is layered glass cards with subtle blur/translucency, not flat solid-only panels.
- **D-02:** Accent color usage is limited to interactive affordances (primary actions, active nav, focus, status emphasis), not large accent-heavy surfaces.
- **D-03:** Default density is comfortable desktop density, with compact treatment only where scanning speed matters.
- **D-04:** Phase 2 visual rollout must apply a single coherent design system to Main shell, Downloader, Checker, and Logs (no partial redesign).

### Navigation and Layout Hierarchy
- **D-05:** Primary app navigation uses a Fluent left rail. For complex pages, inner tabs are allowed as secondary navigation (hybrid model).
- **D-06:** Downloader is a first-class section with its own page scaffold, not just a lightly cleaned-up tab.
- **D-07:** All core sections share a strict scaffold: header zone, primary workspace, contextual side panel, and feedback rail.
- **D-08:** Global utilities (settings/help/theme entry points) remain persistently discoverable from the shell header utility zone.

### Action Feedback System
- **D-09:** Primary feedback channel is inline status/progress, with toast notifications as secondary confirmation and exception signals.
- **D-10:** Toasts auto-dismiss by severity: success/info short, warning/error longer.
- **D-11:** Concurrent feedback events are queued and similar events are collapsed to prevent noise.
- **D-12:** Only destructive actions use blocking confirmation. Routine operations stay non-blocking.

### Downloader Layout and Functionality
- **D-13:** Downloader layout uses a two-column workflow structure.
- **D-14:** Primary functional flow is staged: Parse URL -> Review dependencies -> Confirm download.
- **D-15:** Dense operational detail uses progressive disclosure (advanced sections collapsed by default).
- **D-16:** Current Downloader UX quality is unacceptable and must be corrected in Phase 2: the layout is currently weak and functionality flow is not well thought out.

### Interaction Motion and Rhythm
- **D-17:** Motion level is subtle and purposeful (short transitions for state changes/reveals), avoiding flashy animation.

### Agent's Discretion
- Exact timing values for animations and toasts, as long as they remain subtle/non-blocking and satisfy D-10 and D-17.
- Specific component decomposition for shell scaffold internals, as long as D-05 through D-08 are preserved.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Success Criteria
- `.planning/ROADMAP.md` - Phase 2 goal, requirements mapping, and success criteria.
- `.planning/REQUIREMENTS.md` - UXUI-01, UXUI-02, UXUI-03 (authoritative requirement IDs for this phase).
- `.planning/PROJECT.md` - Milestone goals and product-level constraints.

### Prior Decisions and Continuity
- `.planning/phases/01-qt-platform-migration/01-CONTEXT.md` - locked Phase 1 decisions that Phase 2 builds on.

### Codebase Conventions and Existing Patterns
- `.planning/codebase/CONVENTIONS.md` - UI/threading/style conventions and known anti-patterns.
- `.planning/codebase/STRUCTURE.md` - current package/module layout and extension points.
- `.planning/codebase/ARCHITECTURE.md` - current Qt shell/tab architecture and feedback paths.
- `.planning/codebase/STACK.md` - confirmed stack/runtime constraints for implementation choices.

### Current UI Implementation Baseline
- `factorio_mod_manager/ui/main_window.py` - current QMainWindow header + QTabWidget shell baseline.
- `factorio_mod_manager/ui/downloader_tab.py` - current Downloader information architecture and workflow layout.
- `factorio_mod_manager/ui/styles/dark_theme.qss` - base QSS system to evolve for Fluent Phase 2 styling.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MainWindow` in `factorio_mod_manager/ui/main_window.py`: provides centralized shell composition and is the natural host for left-rail + workspace scaffolding.
- `NotificationManager` in `factorio_mod_manager/ui/widgets.py`: existing non-blocking feedback mechanism to modernize rather than replace.
- `StatusManager` in `factorio_mod_manager/ui/status_manager.py`: existing status channel to retain as part of the feedback rail.
- `dark_theme.qss` + tokens in `factorio_mod_manager/ui/styles/`: styling foundation already centralized for systematic visual redesign.

### Established Patterns
- Qt widget stack already in place (QMainWindow/QTabWidget/QFrame/QTextEdit/QProgressBar).
- Existing code still uses some local inline style strings in screen modules; Phase 2 should consolidate surface/spacing/affordance rules into shared QSS/tokens.
- High-frequency operations already expose progress/status hooks, enabling non-blocking feedback improvements without backend rewrites.

### Integration Points
- Shell/nav refactor primarily intersects `factorio_mod_manager/ui/main_window.py`.
- Downloader structural and staged-flow redesign primarily intersects `factorio_mod_manager/ui/downloader_tab.py`.
- Consistent feedback behavior intersects `factorio_mod_manager/ui/widgets.py`, `factorio_mod_manager/ui/status_manager.py`, and section-level action handlers.

</code_context>

<specifics>
## Specific Ideas

- User explicitly called out the current Downloader tab as visually poor and functionally under-designed.
- Downloader redesign should prioritize clear hierarchy and operational confidence over minimal restyling.
- Phase 2 should remove large dead-space regions and make the workflow legible at a glance.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within Phase 2 boundary.

</deferred>

---

*Phase: 02-fluent-shell-ux*
*Context gathered: 2026-04-10*
