# Factorio Mod Manager

## What This Is

Factorio Mod Manager is a desktop app that helps players download, update, and manage Factorio mods. It currently provides mod downloading with dependency support, update checking for installed mods, and operational logging. This milestone evolves the product into a modern, high-quality desktop UX.

## Core Value

Managing Factorio mods should feel fast, safe, and effortless, even for large mod setups.

## Current Milestone: v1.0 UI Redesign

**Goal:** Deliver a modern Fluent glassy desktop experience with stronger usability and advanced workflow tools.

**Target features:**
- Framework migration to PySide6 for modern UI capabilities
- Pre-migration cleanup: remove dead code (selenium dep, dead credential auth), fix known bugs, write parity checklist
- Full-app Fluent glassy redesign (Downloader, Checker, Logs, shell)
- Bulk queue manager (pause/resume/reorder/cancel)
- Dependency graph viewer
- Profiles and presets for mod sets (including mod enable/disable toggle via mod-list.json)
- Smart update assistant (conflict/risk hints) + per-mod changelog in details popup
- Search and filters overhaul + in-app portal browse
- Settings panel (exposes pre-existing config keys: theme, auto_backup, max_workers)
- In-app onboarding/help

## Requirements

### Validated

- ✓ User can download mods from Factorio portal URLs with dependency handling — existing app behavior
- ✓ User can check installed mods for updates — existing app behavior
- ✓ User can view operation logs in-app — existing app behavior

### Active

- [ ] Pre-migration cleanup: remove dead code and fix known Tkinter bugs before migration (Phase 0)
- [ ] Migrate UI framework to PySide6 to support modern desktop visuals and interactions
- [ ] Redesign all app surfaces for a cohesive Fluent glassy experience
- [ ] Add queue, profiles (incl. mod enable/disable), smart updates, dependency graph, and onboarding improvements
- [ ] Add settings panel exposing pre-existing config keys (theme, auto_backup, auto_refresh, max_workers)
- [ ] Add portal browse, unified search/filter, per-mod changelog in details

### Out of Scope

- New backend service architecture — this milestone focuses on desktop client UX and interaction layer
- Cloud account sync — deferred until local UX and profile model stabilize
- Marketplace publishing workflow changes — deferred to future milestone
- Authenticated download path — all portal downloads use public endpoints; `username`/`token` are dead code with no authenticated endpoint to target

## Context

- Existing codebase is Python desktop app with Tkinter-based UI and reusable core logic.
- .planning/codebase documents are available and should be used as architecture baseline.
- UI quality and UX consistency are currently the primary pain points.

## Constraints

- **Compatibility**: Keep current mod management behavior intact — avoid regressions during UI migration
- **Migration safety**: Use phased cutover with fallback path during transition — reduce delivery risk
- **Desktop-first**: Optimize for Windows desktop usage patterns — app is user’s local utility

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Migrate UI stack from Tkinter to PySide6 | Tkinter cannot deliver true modern glass-style UX | — Pending |
| Scope includes UX + feature additions in one milestone | User requested whole-app redesign plus workflow upgrades | — Pending |
| Visual direction: Fluent glassy | Aligns with requested modern sleek look | — Pending |
| No legacy Tkinter fallback in v1.0 | User requested full migration to new module only | — Pending |
| Phase 0 added: pre-migration cleanup | Gap analysis revealed dead code and known bugs that would complicate Qt migration if not fixed first | — Accepted |
| Credential auth UI out of scope | `username`/`token` fields are dead code — all downloads use public endpoints; no authenticated path exists to target | — Accepted |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-10 after gap analysis — Phase 0 added; REQUIREMENTS.md created; all 33 requirements defined; credential auth scoped out; Phase 1 progress table reset (revert confirmed)*
