# Phase 2: Fluent Shell and UX System - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves alternatives considered.

**Date:** 2026-04-10
**Phase:** 02-fluent-shell-ux
**Areas discussed:** Fluent Visual Language, Action Feedback System, Navigation and Layout Hierarchy, Downloader Layout/Functionality, Interaction Motion and Density

---

## Fluent Visual Language

| Option | Description | Selected |
|--------|-------------|----------|
| Layered glass cards (subtle blur + translucency) | Fluent feel with readability/perf balance | ✓ |
| Solid elevated cards | No blur, depth-only surfaces | |
| High-gloss acrylic everywhere | Strong style, higher noise risk | |

**User's choice:** Layered glass cards (subtle blur + translucency)
**Notes:** User wants stronger quality than current look.

| Option | Description | Selected |
|--------|-------------|----------|
| Accent for interactive affordances only | Accent on actions/focus/active elements | ✓ |
| Accent-heavy surfaces | Large surface tinting | |
| Minimal accent | Mostly monochrome | |

**User's choice:** Accent for interactive affordances only

| Option | Description | Selected |
|--------|-------------|----------|
| Comfortable desktop density | Balanced spacing and scanability | ✓ |
| Compact-first density | Max information density | |
| Large-touch density | Tablet-like spacing | |

**User's choice:** Comfortable desktop density

| Option | Description | Selected |
|--------|-------------|----------|
| Single coherent design system across shell + core screens | Full consistency in Phase 2 | ✓ |
| Shell-only redesign now | Partial scope | |
| Most-used tabs only | Partial scope | |

**User's choice:** Single coherent design system across shell + Downloader + Checker + Logs

---

## Action Feedback System

| Option | Description | Selected |
|--------|-------------|----------|
| Inline status/progress primary, toasts secondary | Balanced, non-blocking feedback | ✓ |
| Toast-first | Highly visible, can be noisy | |
| Status-bar only | Minimal but easy to miss | |

**User's choice:** Inline status + progress as primary, toast as secondary

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-dismiss by severity | Success/info short, warning/error longer | ✓ |
| All persistent | Always manual dismiss | |
| Inline only | No toasts | |

**User's choice:** Auto-dismiss by severity

| Option | Description | Selected |
|--------|-------------|----------|
| Queue and collapse similar events | Reduce spam while preserving signal | ✓ |
| Show every event | Maximum detail, high noise | |
| Show latest only | Cleanest but hides outcomes | |

**User's choice:** Queue and collapse similar events

| Option | Description | Selected |
|--------|-------------|----------|
| Only destructive actions block | Routine flows stay non-blocking | ✓ |
| Always block | Highest friction | |
| Never block | Risk for destructive operations | |

**User's choice:** Only destructive actions block

---

## Navigation and Layout Hierarchy

| Option | Description | Selected |
|--------|-------------|----------|
| Left rail primary | Fluent-aligned global hierarchy | |
| Keep top tabs primary | Minimal change | |
| Hybrid (left rail + inner tabs where needed) | Scalable and flexible | ✓ |

**User's choice:** Hybrid navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Downloader as first-class section with dedicated scaffold | Stable workspace for complex flow | ✓ |
| Downloader as cleaned-up tab | Limited hierarchy gains | |
| Modal workflow | Cleaner shell, more interruption | |

**User's choice:** Downloader as first-class section

| Option | Description | Selected |
|--------|-------------|----------|
| Shared scaffold zones across sections | Header + workspace + contextual panel + feedback rail | ✓ |
| Header-only shared | Partial consistency | |
| No shared scaffold | Maximum variance | |

**User's choice:** Shared scaffold zones across sections

---

## Downloader Layout/Functionality

| Option | Description | Selected |
|--------|-------------|----------|
| Two-column workflow layout | Clear hierarchy and less dead space | ✓ |
| Single-column wizard | Sequential staged page | |
| Keep current page + restyle | Mostly cosmetic change | |

**User's choice:** Two-column workflow layout

| Option | Description | Selected |
|--------|-------------|----------|
| Staged flow (Parse -> Review -> Confirm) | Clear action sequence | ✓ |
| One-click immediate download | Fast, lower clarity | |
| Expert mode always visible | Power-first, crowded | |

**User's choice:** Staged flow

| Option | Description | Selected |
|--------|-------------|----------|
| Progressive disclosure for details | Keep primary path focused | ✓ |
| Always expanded details | High cognitive load | |
| Details in separate dialog | Lower clutter, more friction | |

**User's choice:** Progressive disclosure

**Notes:** User explicitly stated current Downloader tab "looks terrible" and is "not well thought of" for layout and functionality; this is a hard quality constraint for Phase 2.

---

## Interaction Motion and Density

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle purposeful motion | Short, meaningful transitions | ✓ |
| No motion | Instant-only state changes | |
| High motion | More expressive, higher distraction risk | |

**User's choice:** Subtle purposeful motion

---

## Agent's Discretion

- Exact timing constants and easing values for transitions/toasts.
- Internal component splitting as long as locked IA and feedback decisions remain intact.

## Deferred Ideas

None.
