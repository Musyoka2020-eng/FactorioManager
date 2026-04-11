# Phase 5: Dependency Intelligence and Smart Update Guidance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 05-CONTEXT.md - this log preserves alternatives considered.

**Date:** 2026-04-11
**Phase:** 05-dependency-smart-updates
**Areas discussed:** Graph surface, Graph scope and default view, Risk classification policy, Recommended actions and changelog depth

**Discussion note:** User replied `recommended`, so the recommended option for each proposed area was accepted as the locked default.

---

## Graph Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Extend the existing mod details popup | Keep dependency graph and changelog in the current inspection flow; no new shell destination | ✓ |
| Add a dedicated dependency page | Full-page dependency workspace in the shell | |
| Add a separate dependency drawer | Side panel distinct from mod details | |

**User's choice:** Extend the existing mod details popup
**Notes:** Keeps Phase 5 aligned with prior shell and workflow decisions. Entry points remain Checker "View Details" and the global search/details flow.

---

## Graph Scope and Default View

| Option | Description | Selected |
|--------|-------------|----------|
| Simplified direct dependencies by default + full transitive toggle | Low-noise default with optional deeper inspection | ✓ |
| Always show the full transitive graph | Maximum detail, higher visual complexity | |
| Summary-only dependency list | Lowest complexity, but too weak for Phase 5 graph goals | |

**User's choice:** Simplified direct dependencies by default + full transitive toggle
**Notes:** Recommended path keeps the first view readable while still satisfying the full-graph requirement.

---

## Risk Classification Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Balanced-conservative | `Safe` only for clean dependency situations; ambiguous changes become `Review`; broken/conflicting states become `Risky` | ✓ |
| Aggressive automation | Treat most updates as safe unless a hard failure is detected | |
| Strict manual review | Push most updates into review/risky, minimizing one-click flow | |

**User's choice:** Balanced-conservative
**Notes:** Rationale should be plain-language and dependency-aware, not based on version numbers alone.

---

## Recommended Actions and Changelog Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Queue only safe updates by default; show changelog delta first | Keeps one-click actions low-risk and changelog review focused | ✓ |
| Queue safe + review items together; show full changelog history flat | Faster bulk path, higher risk and more noise | |
| No batch recommendations; changelog as simple link-out | Lowest implementation risk, weaker Phase 5 outcome | |

**User's choice:** Queue only safe updates by default; show changelog delta first
**Notes:** `Review` and `Risky` items remain manually queueable through the existing queue flow. Older changelog history stays accessible after the initial installed-to-latest delta.

---

## Agent's Discretion

- Exact dependency graph rendering mechanics inside the details popup.
- Exact layout of the smart guidance surface in Checker.
- Exact changelog expansion/collapse treatment.

## Deferred Ideas

- Dedicated dependency dashboard page.
- Fully automatic queueing of `Review` or `Risky` updates.