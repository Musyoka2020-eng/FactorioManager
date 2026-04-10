---
phase: 1
slug: qt-platform-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `py_compile` (syntax), `grep` (parity assertions), manual behavioral verification |
| **Config file** | none — no automated test suite for UI code |
| **Quick run command** | `python -m py_compile factorio_mod_manager/ui/main_window.py factorio_mod_manager/ui/downloader_tab.py factorio_mod_manager/ui/checker_tab.py factorio_mod_manager/ui/logger_tab.py factorio_mod_manager/ui/widgets.py factorio_mod_manager/ui/status_manager.py` |
| **Full suite command** | `grep -r "import tkinter\|from tkinter" factorio_mod_manager/ui/ && echo FAIL || echo PASS` (parity: no Tkinter in ui/) |
| **Estimated runtime** | ~5 seconds (compile checks) |

---

## Sampling Rate

- **After every task commit:** Run quick compile check
- **After every plan wave:** Run full Tkinter-purge grep + compile sweep
- **Before `/gsd-verify-work`:** Manual behavioral walkthrough against PARITY-CHECKLIST.md
- **Max feedback latency:** ~5 seconds (automated), plus manual verify at wave end

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | PLAT-01 | — | N/A | compile | `python -m py_compile factorio_mod_manager/main.py` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | PLAT-01 | — | N/A | grep | `test -f factorio_mod_manager/ui/styles/dark_theme.qss && echo PASS` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | PLAT-01 | — | N/A | compile | `python -m py_compile factorio_mod_manager/ui/main_window.py factorio_mod_manager/ui/status_manager.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | PLAT-01 | — | N/A | compile | `python -m py_compile factorio_mod_manager/ui/widgets.py` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | PLAT-03 | — | N/A | compile | `python -m py_compile factorio_mod_manager/ui/logger_tab.py factorio_mod_manager/utils/logger.py` | ❌ W0 | ⬜ pending |
| 01-05-01 | 05 | 2 | PLAT-03 | — | N/A | compile | `python -m py_compile factorio_mod_manager/ui/downloader_tab.py` | ❌ W0 | ⬜ pending |
| 01-06-01 | 06 | 2 | PLAT-03 | — | N/A | compile | `python -m py_compile factorio_mod_manager/ui/checker_tab.py` | ❌ W0 | ⬜ pending |
| 01-final | — | end | PLAT-02 | — | No Tkinter code paths | grep | `grep -r "import tkinter\|from tkinter\|ttk\\." factorio_mod_manager/ui/ && echo FAIL_tkinter_found \|\| echo PASS_no_tkinter` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No automated test framework is introduced in Phase 1 (UI migration only — no business logic changes). All existing `core/` and `utils/` logic is unchanged. Verification is:
1. **Compile checks** — `py_compile` on each rewritten UI file (fast, catches syntax errors and import resolution)
2. **Grep assertions** — no Tkinter imports survive in `ui/`
3. **Manual behavioral walkthrough** — PARITY-CHECKLIST.md (125 items) at phase end

*Existing infrastructure covers phase requirements — no Wave 0 test scaffolding needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Window launches maximized, min 1100×750 | PLAT-01 | Requires display | Launch app, verify window state and resize constraint |
| Toast notifications appear top-right with fade | PLAT-03 | Requires display + timer | Trigger download/scan, verify toast placement and dismiss animation |
| Downloader 500 ms debounce | PLAT-03 | Requires interactive timing | Type URL, verify no immediate network call; wait 500 ms, verify lookup fires |
| Checker auto-scan ~3s on first tab open | PLAT-03 | Requires display + timer | Open Checker tab fresh, verify scan starts after ~3 seconds |
| Log color coding (blue/green/red/yellow/gray) | PLAT-03 | Requires display | Trigger operations, check log line colors in Logs tab |
| Full PARITY-CHECKLIST.md walkthrough | PLAT-03 | Requires interactive use | Run all 125 PARITY-CHECKLIST.md items against the running Qt app |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (automated compile/grep)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
