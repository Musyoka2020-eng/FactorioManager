# Phase 5: Dependency Intelligence and Smart Update Guidance - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Add read-only dependency visibility plus explainable smart update guidance to the existing desktop workflows.

This phase includes:
- A read-only dependency graph for a selected mod
- Simplified and full transitive graph views
- Clear required, optional, incompatible, missing, and expansion/DLC dependency states
- Safe / review / risky update classifications with rationale
- Assistant-recommended batch actions that feed into the shared queue workflow
- Per-mod changelog content inside the mod details popup

This phase does not add a new shell destination, editable dependency management, or fully automatic execution of risky updates.

</domain>

<decisions>
## Implementation Decisions

### Dependency Graph Surface
- **D-01:** Use the existing mod details popup as the primary inspection surface for Phase 5. Add dependency and changelog views there instead of creating a new shell page or standalone dependency screen.
- **D-02:** Dependency graph entry points should come from existing mod-inspection paths: Checker "View Details" and the global search result details flow.
- **D-03:** The dependency graph is read-only. This phase helps users understand impact; it does not provide direct editing of dependency state.
- **D-04:** Exact graph rendering style (tree, node-link, or hybrid) is agent's discretion, but it must optimize for desktop readability inside the details popup rather than requiring a heavy standalone canvas workflow.

### Graph Scope and State Visibility
- **D-05:** Default graph mode is simplified and shows the selected mod's direct dependency footprint first.
- **D-06:** Users can switch to a full mode that expands to the complete transitive dependency graph.
- **D-07:** Both views must clearly distinguish required, optional, incompatible, missing, and expansion/DLC dependency states.
- **D-08:** Simplified mode may visually de-emphasize optional branches, but optional dependencies still need to remain identifiable.
- **D-09:** Expansion/DLC requirements should be surfaced as non-downloadable requirements, not treated as normal downloadable mods.

### Smart Update Guidance Policy
- **D-10:** Smart update guidance belongs in the Checker/update workflow, close to selection and queue actions, not in a separate shell destination.
- **D-11:** Use a balanced-conservative classification policy. `Safe` applies only when an update introduces no missing required dependencies, no incompatibilities, no expansion/DLC requirement issues, and no notable dependency graph risk.
- **D-12:** `Review` applies when an update is likely acceptable but changes direct or transitive dependency footprint, affects optional branches in a meaningful way, or otherwise needs a quick human review of rationale or changelog before queueing.
- **D-13:** `Risky` applies when incompatibilities, missing required dependencies, expansion/DLC requirements, or high-impact dependency changes could destabilize the current mod setup.
- **D-14:** Risk guidance should be explainable. Each recommendation must include plain-language rationale; the system should not rely on opaque scoring or version-number-only heuristics.

### Recommended Actions and Changelog Behavior
- **D-15:** Assistant-recommended one-click batch actions should queue only `Safe` updates by default.
- **D-16:** `Review` and `Risky` items remain manually queueable through the existing queue workflow, but the assistant should not bulk-enqueue them automatically.
- **D-17:** The mod details popup should include a changelog view for both installed and portal-backed mod details whenever changelog data is available.
- **D-18:** Changelog presentation should default to the installed-version-to-latest delta first when the installed version is known, with older history still accessible below or via expansion.

### Agent's Discretion
- Exact graph widget and visualization mechanics, as long as D-01 through D-09 are preserved.
- Exact layout of smart guidance inside the Checker workflow, as long as it stays close to update selection and queue actions per D-10.
- Exact changelog collapse/expand mechanics, as long as D-17 and D-18 are preserved.

</decisions>

<specifics>
## Specific Ideas

- User selected the recommended path for all discussed Phase 5 gray areas.
- Phase 5 should feel like an inspection-and-guidance upgrade to existing workflows, not a new destination users have to learn.
- Smart update guidance should bias toward clear reasoning and conservative bulk actions rather than silent automation.
- The safest one-click path is "queue safe updates"; anything ambiguous should stay visible for human review.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Requirements
- `.planning/ROADMAP.md` - Phase 5 goal, dependency, and success criteria.
- `.planning/REQUIREMENTS.md` - requirement IDs `DEPS-01`, `DEPS-02`, `DEPS-03`, `UPDT-01`, `UPDT-02`, `UPDT-03`.
- `.planning/PROJECT.md` - milestone constraints, desktop-first posture, and accepted scope boundaries.

### Prior Locked UX and Workflow Decisions
- `.planning/phases/02-fluent-shell-ux/02-CONTEXT.md` - left-rail shell, header utility zone, and non-blocking feedback conventions that Phase 5 must extend.
- `.planning/phases/03-search-filter-settings/03-CONTEXT.md` - global search/details flow and centralized shell utility patterns that Phase 5 should reuse.
- `.planning/phases/04-queue-profiles/04-CONTEXT.md` - shared queue model, embedded workflow controls, and queue badge/drawer behavior that recommended actions must feed into.

### Codebase Conventions and Architecture
- `.planning/codebase/ARCHITECTURE.md` - current UI/core split, worker patterns, and inspection/update data flow.
- `.planning/codebase/CONVENTIONS.md` - thread-safety, UI, and logging conventions for new Phase 5 work.
- `.planning/codebase/STRUCTURE.md` - package boundaries and likely extension points for dependency/risk/changelog additions.
- `.planning/codebase/STACK.md` - runtime/dependency constraints and confirmed use of BeautifulSoup-backed changelog scraping.

### Existing Implementation Baseline
- `factorio_mod_manager/core/mod.py` - current dependency categories, expansion/DLC handling, and raw mod metadata model.
- `factorio_mod_manager/core/portal.py` - current dependency parsing and changelog-fetching capabilities.
- `factorio_mod_manager/ui/mod_details_dialog.py` - existing mod inspection popup to extend for dependency graph and changelog views.
- `factorio_mod_manager/ui/search_bar.py` - global search result flow that already routes into mod details.
- `factorio_mod_manager/ui/checker_tab.py` - current installed-mod inspection and batch update workflow where smart guidance should surface.
- `factorio_mod_manager/ui/queue_controller.py` - authoritative shared queue path for assistant-recommended actions.
- `factorio_mod_manager/ui/update_queue_job.py` - current queue-backed batch update execution wrapper.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FactorioPortalAPI.get_mod_dependencies(...)` and `FactorioPortalAPI.get_mod_changelog(...)` already expose most of the raw data this phase needs.
- `Mod` in `factorio_mod_manager/core/mod.py` already carries required, optional, incompatible, and expansion dependency buckets, plus raw portal data and installed/latest version state.
- `ModDetailsDialog` is already the standard inspection surface for installed and portal results.
- `CheckerTab` already owns selected-mod update actions and is the natural surface for explainable guidance close to update decisions.
- `QueueController` and `UpdateQueueJob` already provide the queue-backed path for batch update actions.
- `GlobalSearchBar` and `SearchResultsPopup` already route users into the details popup from the shell header.

### Established Patterns
- Inspection flows currently use dialogs/popups instead of full-page navigation, which supports extending the details popup for Phase 5.
- Shared queue behavior is already centralized and should remain the only execution path for assistant-recommended batch actions.
- Background work already uses Qt worker patterns (`QThread` + signals/slots), which Phase 5 should follow for dependency/changelog fetches.
- Previous phases favored embedded workflow enhancements over new shell destinations; Phase 5 should preserve that pattern.

### Integration Points
- Dependency graph and changelog views should extend `ModDetailsDialog` rather than introducing a second inspection surface.
- Smart risk classifications and batch recommendations should connect to `CheckerTab` selection state and queue actions.
- Queue-safe recommendations should create or reuse `QueueOperation` update jobs instead of adding a bypass path.
- No graph visualization widget exists yet, so Phase 5 introduces a new read-only visualization layer while anchoring it inside existing inspection flow.

</code_context>

<deferred>
## Deferred Ideas

- Dedicated left-rail dependency dashboard or analytics page - deferred; Phase 5 should stay inside existing details and Checker workflows.
- Fully automatic queueing of `Review` or `Risky` updates - deferred; Phase 5 keeps those human-directed.

</deferred>

---

*Phase: 05-dependency-smart-updates*
*Context gathered: 2026-04-11*