# Phase 3: Search, Filtering, and Settings Foundation - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Add unified search/sort/filter plus centralized settings, theming, and safe credential handling.

This phase includes:
- One unified search experience across installed, downloadable, and queued mods
- Filter/sort by status and priority in active workflows
- In-app Factorio portal browse by keyword and category
- Centralized settings for paths, behavior, and appearance
- Theme mode switching (dark/light/system) with immediate visual feedback
- UI for existing config keys: `max_workers`, `auto_backup`, `auto_refresh`
- Credential handling hardening by removing obsolete username/token concepts

This phase does not add queue execution controls, profile workflows, dependency graph features, or onboarding flows.

</domain>

<decisions>
## Implementation Decisions

### Unified Search Architecture
- **D-01:** Add a global search entry in the shell header utility zone.
- **D-02:** Global search supports keyboard shortcut `Ctrl+K` and a visible clickable entry point.
- **D-03:** Unified results are grouped by source: Installed, Queued, Portal.
- **D-04:** Default ranking order is Installed first, then Queued, then Portal.
- **D-05:** Selecting a result opens a details popup by default (not immediate page navigation).

### Filter and Sort Contract
- **D-06:** Use a shared core filter/sort contract across lists, with context-specific extras per page.
- **D-07:** Priority in Phase 3 means operational priority derived from workflow state (for example outdated/selected/queued urgency), not manual user tagging.
- **D-08:** Status and priority controls should be available without forcing users to leave the current workflow context.

### Portal Browse UX
- **D-09:** Portal browse is delivered inside Downloader (no new left-rail destination for Phase 3).
- **D-10:** Support keyword search plus top category chips backed by portal queries.
- **D-11:** Portal browse should maintain the current staged Downloader workflow structure where possible.

### Settings Information Architecture
- **D-12:** Implement one centralized settings page with grouped sections/cards: Paths, Behavior, Appearance, Advanced.
- **D-13:** Settings entry point lives in the shell header utility zone.
- **D-14:** Use native form controls for required keys: numeric control for `max_workers`, toggles for `auto_backup` and `auto_refresh`.
- **D-15:** Settings edits apply on explicit Save (not per-field immediate commit).

### Theme Behavior
- **D-16:** Theme modes are Dark, Light, and System.
- **D-17:** Theme changes should reflect immediately when user applies/saves settings.
- **D-18:** In System mode, app theme auto-switches if OS theme changes while app is open.

### Credential Safety Policy
- **D-19:** Remove username/token concept from settings and configuration model entirely.
- **D-20:** Treat previous credential-related fields as dead legacy and remove related code paths during this phase.

### Agent's Discretion
- Exact global search UI composition (popup, overlay, or panel) as long as D-01 through D-05 are preserved.
- Exact schema for operational-priority categories as long as it is workflow-state-derived per D-07.
- Exact settings visual layout and card ordering within the required sections.
- Concrete save/validation UX details, provided explicit Save behavior (D-15) is preserved.

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants obsolete credential concepts removed: username/token should not remain as active product concepts.
- Unified search should feel like a command surface for fast discovery while still exposing source-grouped context.
- Portal browsing should stay close to download flow to avoid context switching.
- Settings should centralize common controls but still keep workflows focused; users should not need to hunt across tabs for key config behavior.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Requirements
- `.planning/ROADMAP.md` - Phase 3 goal, dependencies, and success criteria.
- `.planning/REQUIREMENTS.md` - SRCH-01, SRCH-02, SRCH-03, SETT-01, SETT-02, SETT-03.
- `.planning/PROJECT.md` - milestone constraints and accepted product decisions.

### Prior Locked UX Decisions
- `.planning/phases/02-fluent-shell-ux/02-CONTEXT.md` - shell/navigation and feedback conventions that Phase 3 must extend, not break.

### Existing Implementation Baseline
- `factorio_mod_manager/ui/main_window.py` - current left rail shell and header utility region.
- `factorio_mod_manager/ui/downloader_tab.py` - existing portal search behavior, staged downloader flow, and integration point for in-page portal browse.
- `factorio_mod_manager/ui/checker_tab.py` - current search/filter/sort controls and table workflow context.
- `factorio_mod_manager/ui/checker_presenter.py` - central filtering/sorting logic to generalize for shared contract.
- `factorio_mod_manager/utils/config.py` - existing config defaults and persistence surface (`theme`, `auto_backup`, `auto_refresh`, `max_workers`, legacy credential fields).
- `factorio_mod_manager/core/portal.py` - portal search APIs used for keyword/category browse.

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` - coding/threading/UI conventions.
- `.planning/codebase/STRUCTURE.md` - package boundaries and where to add new UI/settings/search modules.
- `.planning/codebase/STACK.md` - runtime/dependency constraints.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CheckerPresenter.filter_mods(...)` already encapsulates search/filter/sort for installed mods and should inform shared contract extraction.
- `DownloaderTab` already has debounced portal keyword search (`SearchWorker` + 500 ms timer) and can be extended for category browse.
- `MainWindow` header and shell already exist, making header utility entry points (search/settings) a low-friction extension.
- `Config` singleton already persists required keys (`theme`, `auto_backup`, `auto_refresh`, `max_workers`) so Phase 3 can focus on UX and safe state handling.

### Established Patterns
- Non-blocking worker pattern uses `QThread` + signals/slots across UI flows.
- Fluent shell direction from Phase 2 uses consistent page header + workspace + side panel rhythm.
- Notifications/status updates are already centralized via `NotificationManager` and `StatusManager`.

### Integration Points
- Global search entry should integrate with `MainWindow` header and route queries into Checker/Downloader/queue datasets.
- Shared filter/sort logic should be consumed by existing list surfaces without breaking current checker workflows.
- Settings UI should connect to `utils.config.config` and become the canonical config editing surface.
- Credential removal must include config defaults and any stale references in downloader/portal constructors and UI.

</code_context>

<deferred>
## Deferred Ideas

- Adding a dedicated new left-rail Portal page is deferred; Phase 3 keeps portal browse inside Downloader.
- Manual user-defined priority tags are deferred; Phase 3 priority is operational-state-based.

</deferred>

---

*Phase: 03-search-filter-settings*
*Context gathered: 2026-04-11*
