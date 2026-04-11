# Phase 4: Queue Control and Profile Workflows - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver shared queue control plus profile and preset workflows for the existing desktop app. This phase covers queue actions for downloads, updates, and profile apply operations; profile save/apply flows with diff preview and undo confidence; and individual mod enable or disable via `mod-list.json`.

This phase does not add dependency graph views, smart update risk classification, onboarding, or a new dedicated queue page in the shell.

</domain>

<decisions>
## Implementation Decisions

### Queue Scope and Visibility
- **D-01:** Phase 4 uses one shared operation queue for downloads, updates, and profile apply actions.
- **D-02:** Primary queue controls stay embedded inside existing workflow surfaces (Downloader and Checker-related flows), not in a dedicated left-rail queue page.
- **D-03:** The shell header gets a global queue badge that opens the current queue panel so queue state stays visible from anywhere in the app.

### Queue Behavior and Recovery
- **D-04:** Default queue policy is continue-on-failure: a failed item should not stop the rest of the queue automatically.
- **D-05:** Failed items move into an actionable failed state with retry, inspect, and skip-style recovery actions.
- **D-06:** Queue state must clearly distinguish queued, running, paused, completed, failed, and canceled outcomes so users can understand what happened to each item.

### Profiles and Presets
- **D-07:** A profile represents the desired enabled mod set, not just the exact files currently present on disk.
- **D-08:** Applying a profile may enqueue missing mods for download so the target profile can be reached from the current local state.
- **D-09:** The app ships a small curated preset set for seeding profiles, centered on categories like Vanilla+, QoL, and Logistics/Rail.

### Apply Preview and Rollback
- **D-10:** Profile apply always shows a full diff preview before execution.
- **D-11:** The apply preview must explicitly show add, remove, enable, disable, and download actions.
- **D-12:** Profile apply requires explicit confirmation before changes start.
- **D-13:** The app provides one-click undo back to the pre-apply snapshot.

### Mod Enable or Disable Workflow
- **D-14:** Day-to-day mod enable or disable lives in the installed-mods workflow surface, with profile flows reusing the same underlying state model.
- **D-15:** Disabling a mod keeps its ZIP installed locally and changes only `mod-list.json` by default.

### Agent's Discretion
- Exact embedded queue panel layout inside Downloader and Checker, as long as D-01 through D-06 hold.
- Exact visual form of the header queue badge and panel trigger, as long as queue state remains globally visible.
- Exact mod selections inside each curated preset category, as long as the preset families remain small and aligned with Vanilla+, QoL, and Logistics/Rail.
- Snapshot storage format and retention beyond the immediate rollback action, as long as D-13 remains available for the most recent apply.

</decisions>

<specifics>
## Specific Ideas

- Shared queue, but not as a standalone page: control should feel close to the workflow where the action started.
- Queue visibility should behave like a global utility, via a header badge that opens the active queue panel.
- Profiles should feel like desired-state switching, not just local file bookmarking.
- Preset seeds should be helpful but limited in number: Vanilla+, QoL, and Logistics/Rail are the intended starter families.
- Disabled mods should remain installed for fast re-enable and lower-risk rollback.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Requirements
- `.planning/ROADMAP.md` §Phase 4 — authoritative goal, dependency, and success criteria for queue control and profile workflows.
- `.planning/REQUIREMENTS.md` §Queue Management and §Profiles and Presets — requirement IDs `QUEUE-01`, `QUEUE-02`, `PROF-01`, `PROF-02`, `PROF-03`, `PROF-04`, `PROF-05`.
- `.planning/PROJECT.md` — milestone-level constraints, desktop-first posture, and accepted decisions inherited by this phase.

### Prior Locked UX and Shell Decisions
- `.planning/phases/02-fluent-shell-ux/02-CONTEXT.md` — left-rail shell, header utility zone, and non-blocking feedback conventions that Phase 4 must extend.
- `.planning/phases/03-search-filter-settings/03-CONTEXT.md` — global header utility pattern, settings snapshot expectations, and existing page organization that Phase 4 must preserve.

### Codebase Conventions and Existing Architecture
- `.planning/codebase/ARCHITECTURE.md` — current UI/core split, worker patterns, and operation flow boundaries.
- `.planning/codebase/CONVENTIONS.md` — thread-safety, logging, and UI conventions for new queue/profile code.
- `.planning/codebase/STRUCTURE.md` — current module boundaries and likely extension points for new queue/profile modules.
- `.planning/codebase/CONCERNS.md` — existing gap note that `mod-list.json` enable or disable support does not yet exist.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `factorio_mod_manager/ui/main_window.py` — already has a header utility zone and `QStackedWidget` shell; natural host for a global queue badge without adding a new navigation destination.
- `factorio_mod_manager/ui/downloader_tab.py` — already owns asynchronous download execution, per-mod status display, and progress reporting; strong integration point for queue item controls and queue-backed download jobs.
- `factorio_mod_manager/ui/checker_tab.py` + `factorio_mod_manager/ui/checker_logic.py` — already own installed-mod selection and batch actions; natural home for enable/disable controls and update actions that join the shared queue.
- `factorio_mod_manager/ui/settings_page.py` — already uses snapshot/original-value handling; useful reference for apply preview, revert expectations, and explicit-confirm workflows.
- `factorio_mod_manager/core/checker.py` — already scans installed ZIPs and understands local mod inventory, which can seed profile creation and diff generation.
- `factorio_mod_manager/core/downloader.py` — already resolves dependencies and runs concurrent downloads, which can become one queue-backed operation type.

### Established Patterns
- Current Qt UI uses page-local workspaces with shell-level utilities in the header, matching the decision to keep queue controls embedded while exposing a global badge.
- Background work already follows `QThread` + signals/slots in current Qt pages; new queue orchestration should follow the same model.
- Non-blocking notifications and status feedback are already centralized and should remain the secondary feedback path behind inline queue state.

### Integration Points
- Queue orchestration will need to bridge Downloader jobs, Checker update jobs, and profile apply jobs behind one shared operation model.
- Profile creation and diff preview will likely draw from the installed-mod inventory surfaced by `CheckerTab` / `ModChecker`.
- `Config` currently stores app settings only; profile, preset, queue, and snapshot persistence will require new storage surfaces rather than extending existing settings keys blindly.
- No existing `profile`, `preset`, queue domain module, or `mod-list.json` writer exists yet, so Phase 4 is a net-new capability layered onto current Qt workflows.

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 4 scope.

</deferred>

---

*Phase: 04-queue-profiles*
*Context gathered: 2026-04-11*