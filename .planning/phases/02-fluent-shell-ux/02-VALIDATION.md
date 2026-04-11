---
phase: 02
slug: fluent-shell-ux
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Phase 2 is a pure UI refactor — no new business logic. Validation focuses on smoke tests, structural assertions, and visual/interaction checkpoints.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already used in project) |
| **Config file** | pyproject.toml `[tool.pytest]` section |
| **Quick run command** | `python -c "from factorio_mod_manager.ui.main_window import MainWindow; print('OK')"` |
| **Full suite command** | `pytest tests/ -x -q 2>/dev/null || python -m py_compile factorio_mod_manager/ui/*.py && echo "compile OK"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick import smoke test
- **After every plan wave:** Run full compile + grep audit
- **Before `/gsd-verify-work`:** Full suite green + inline style grep returns 0
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 02-01-01 | 01 | 1 | UXUI-01 | Tokens/QSS have no user-input injection path | compile | `python -c "from factorio_mod_manager.ui.styles.tokens import ACCENT"` | ⬜ pending |
| 02-01-02 | 01 | 1 | UXUI-03 | Notification duration defaults come from severity map, not caller-supplied unbounded values | unit | `python -m pytest tests/test_notification_manager.py -x -q` | ⬜ pending |
| 02-02-01 | 02 | 2 | UXUI-02 | Shell exposes no unauthenticated privileged action via nav rail | smoke | `python -c "from factorio_mod_manager.ui.main_window import MainWindow; print('OK')"` | ⬜ pending |
| 02-02-02 | 02 | 2 | UXUI-02 | Downloader staged flow | smoke | `python -c "from factorio_mod_manager.ui.downloader_tab import DownloaderTab; print('OK')"` | ⬜ pending |
| 02-03-01 | 03 | 3 | UXUI-01 | No inline setStyleSheet calls remain | grep | `grep -rn "setStyleSheet" factorio_mod_manager/ui/ --include="*.py" \| grep -v "dark_theme\|NotificationManager\|apply_stylesheet" \| wc -l` returns 0 | ⬜ pending |
| 02-03-02 | 03 | 3 | UXUI-02 | Checker and Logs pages compile cleanly | compile | `python -c "from factorio_mod_manager.ui.checker_tab import CheckerTab; from factorio_mod_manager.ui.logger_tab import LoggerTab; print('OK')"` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_notification_manager.py` — unit tests for severity-aware duration defaults and event_key deduplication (D-10, D-11)

*If testing infrastructure is absent: `pip install pytest` and create `tests/__init__.py`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Left rail visual appearance and active state indicator | UXUI-02 | Qt widget rendering requires human eye | Run app, click each nav item, verify left border turns accent blue on active item |
| Fluent glass card surfaces in Downloader info card | UXUI-01 | Visual quality judgment | Run app, load a mod, verify info card has elevated surface appearance |
| Toast deduplication under rapid events | UXUI-03 | Timing-dependent visual behavior | Trigger two rapid downloads with same mod; verify one toast collapses/updates, not two stack |
| Staged Downloader flow progression | UXUI-02 | Interactive flow validation | Enter URL → Stage 2 appears → confirm → Stage 3 appears → download runs |
