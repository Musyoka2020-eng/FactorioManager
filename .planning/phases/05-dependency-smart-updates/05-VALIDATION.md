---
phase: 5
slug: dependency-smart-updates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ^7.4.0 |
| **Config file** | none — pytest finds `tests/` by convention |
| **Quick run command** | `pytest tests/core/test_dependency_graph.py tests/core/test_update_guidance.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds (no Qt, pure Python core tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/ -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green + manual verification of all 6 success criteria

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | DEPS-03 | — | N/A | unit | `pytest tests/core/test_dependency_graph.py -x` | ❌ Wave 0 | ⬜ pending |
| 05-01-02 | 01 | 1 | UPDT-01 | — | N/A | unit | `pytest tests/core/test_update_guidance.py -x` | ❌ Wave 0 | ⬜ pending |
| 05-02-01 | 02 | 2 | DEPS-01, DEPS-02, DEPS-03 | — | N/A | manual | — | ❌ | ⬜ pending |
| 05-02-02 | 02 | 2 | UPDT-03 | — | N/A | manual | — | ❌ | ⬜ pending |
| 05-03-01 | 03 | 2 | UPDT-01, UPDT-02 | — | N/A | manual | — | ❌ | ⬜ pending |
| 05-04-01 | 04 | 3 | DEPS-01, DEPS-02, DEPS-03, UPDT-01, UPDT-02, UPDT-03 | — | N/A | manual | — | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/test_dependency_graph.py` — stubs for DEPS-03 dep traversal and DepState logic
- [ ] `tests/core/test_update_guidance.py` — stubs for UPDT-01 all three classification tiers + edge cases

*Existing conftest.py and pytest infrastructure are sufficient — no new framework installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dependency tree renders in Dependencies tab with correct state chips | DEPS-01, DEPS-03 | Requires Qt widget display | Open "View Details" for any mod, click "Dependencies" tab, verify group nodes and colored chip states |
| Simplified/Full toggle changes tree expansion depth | DEPS-02 | Requires interacting with Qt button group | Toggle simplified ↔ full, verify transitive nodes appear/collapse |
| Changelog delta section shows correct installed→latest range | UPDT-03 | Requires network + known version data | Open outdated mod details, click "Changelog" tab, verify delta header version range |
| SmartUpdateStrip scope rule: count follows row selection | UPDT-02 | Requires Qt selection state | Select rows in Checker, verify strip count updates |
| "Queue Safe Updates" creates visible queue entry | UPDT-02 | Requires full queue workflow | Click action, verify queue strip and drawer show new operation |
| Deep-link from Checker panel opens Dependencies tab directly | DEPS-01 | Requires cross-widget routing | Click "View Details" in Checker guidance panel, verify dialog opens to Dependencies tab |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (core tests only — no Qt)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
