# Phase 1: Qt Platform Migration — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 01-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 01-qt-platform-migration
**Areas discussed:** Code organization, Threading model, Phase 1 visual scope, Window and layout structure

---

## Code Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Replace-in-place — rewrite ui/ directly | Rename/delete existing ui/, create new Qt equivalents with same filenames. Phase 2 works directly in ui/. | ✓ |
| Side-by-side — build ui_qt/ in parallel | Create ui_qt/ alongside existing ui/, migrate tab by tab, flip entrypoint, delete ui/ at end of Phase 1. | |
| Monolithic start — single qt_main.py first | One big Qt file to start, split into proper modules later. | |

**Same filenames or rename:**
| Option | Selected |
|--------|----------|
| Keep same filenames — just rewrite the contents | ✓ |
| Rename files to qt_*.py | |
| Agent's discretion | |

**Plan granularity:**
| Option | Selected |
|--------|----------|
| All at once — full ui/ rewrite as one block | |
| Per-module plans — one plan per UI file | ✓ |
| Two waves — shell first, then tabs | |

**checker_logic.py / checker_presenter.py:**
| Option | Selected |
|--------|----------|
| Keep separate | |
| Fold into checker_tab.py | |
| Agent's discretion | ✓ |

**Dependencies:**
| Option | Selected |
|--------|----------|
| Add PySide6, clean dead deps, done | ✓ |
| Also update PyInstaller spec in Phase 1 | |
| Defer PyInstaller spec update | |

**Full cutover confirmation:**
| Option | Selected |
|--------|----------|
| Full cutover, no old code kept (already decided) | ✓ |

---

## Threading Model

| Option | Description | Selected |
|--------|-------------|----------|
| QThread + signals/slots (Qt-native) | Worker emits signals; UI slots update on main thread. | ✓ (agent chose as best) |
| Python threads + Qt signals (hybrid) | Python thread starts work, emits Qt signals back to UI. | |
| Python threads + QTimer.singleShot bridge | Closest translation of tkinter after() pattern. | |

**User's choice:** "pick the best" → agent selected QThread + signals/slots

**Worker granularity:**
| Option | Selected |
|--------|----------|
| Dedicated QThread subclasses per operation | ✓ |
| QThreadPool + QRunnable | |
| Agent's discretion | |

**Logger approach:**
| Option | Selected |
|--------|----------|
| QTimer polling Python Queue | |
| Qt signal from custom logging handler | |
| Agent's discretion | ✓ |

---

## Phase 1 Visual Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Bare functional Qt — Phase 2 handles all styling | Bare Qt widgets, no custom styling. Fast Phase 1. | |
| Match current dark theme in Qt | Reproduce #0e0e0e / #0078d4 / #e0e0e0 colors in Qt. Familiar UI immediately. | ✓ |
| Qt dark system palette — no custom colors | Use QApplication.setPalette dark palette. | |

**Theme implementation:**
| Option | Selected |
|--------|----------|
| QSS stylesheet replicating Tkinter colors | ✓ |
| Per-widget inline styling | |
| Agent's discretion | |

---

## Window and Layout Structure

| Option | Description | Selected |
|--------|-------------|----------|
| QMainWindow + QTabWidget (natural Qt equivalent) | Mirrors Tkinter root + ttk.Notebook. Built-in status bar slot. | |
| Plain QWidget root + manual layout | More control, no built-in status bar. | |
| Agent's discretion | | ✓ |

**Notification/toast:**
| Option | Selected |
|--------|----------|
| Qt overlay widget (absolute positioned) | |
| No floating overlay — use status bar | |
| Third-party toast library | |
| Agent's discretion | ✓ |

---

## Agent's Discretion

- `checker_logic.py` / `checker_presenter.py`: keep separate or fold into checker_tab (agent chooses)
- Logger queue-to-Qt bridge: QTimer polling vs Qt signal handler (agent chooses)
- StatusManager Qt implementation (agent chooses)
- QMainWindow vs QWidget root (agent chooses; QMainWindow+QTabWidget is the obvious fit)
- Notification overlay mechanism (agent chooses)

## Deferred Ideas

- PyInstaller spec update for PySide6 (user explicitly deferred to post-Phase 1 or packaging phase)
