# Factorio Mod Manager

## What This Is

Factorio Mod Manager is a desktop app that helps players download, update, and manage Factorio mods. It currently provides mod downloading with dependency support, update checking for installed mods, and operational logging. This milestone evolves the product into a modern, high-quality desktop UX.

## Core Value

Managing Factorio mods should feel fast, safe, and effortless, even for large mod setups.

## Current Milestone: v1.0 Ui Redesign

**Goal:** Deliver a modern Fluent glassy desktop experience with stronger usability and advanced workflow tools.

**Target features:**
- Framework migration to PySide6 for modern UI capabilities
- Full-app Fluent glassy redesign (Downloader, Checker, Logs, shell)
- Bulk queue manager (pause/resume/reorder/cancel)
- Dependency graph viewer
- Profiles and presets for mod sets
- Smart update assistant (conflicts/risk hints)
- Search and filters overhaul
- Settings and theming panel
- In-app onboarding/help

## Requirements

### Validated

- ✓ User can download mods from Factorio portal URLs with dependency handling — existing app behavior
- ✓ User can check installed mods for updates — existing app behavior
- ✓ User can view operation logs in-app — existing app behavior

### Active

- [ ] Migrate UI framework to support modern desktop visuals and interactions
- [ ] Redesign all app surfaces for a cohesive Fluent glassy experience
- [ ] Add queue, profiles, smart updates, dependency graph, and onboarding improvements

### Out of Scope

- New backend service architecture — this milestone focuses on desktop client UX and interaction layer
- Cloud account sync — deferred until local UX and profile model stabilize
- Marketplace publishing workflow changes — deferred to future milestone

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
*Last updated: 2026-04-10 after full reset — reverted to pre-Phase 1 baseline (3d9bbc1); ready to re-execute Phase 1*
