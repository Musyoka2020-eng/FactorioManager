# Phase 01 — Plan 05 SUMMARY

## Plan: 01-05 — DownloaderTab QThread

**Status:** Complete  
**Commit:** `a6c8b51`  
**Wave:** 3

---

## Objectives Achieved

- Rewrote `factorio_mod_manager/ui/downloader_tab.py` from Tkinter → PySide6 QWidget
- All Tkinter (`threading.Thread`, `root.after_idle`) removed (423 insertions, 1299 deletions)
- PLAT-03 requirement addressed: Downloader tab fully migrated

---

## Artifacts Created / Modified

| File | Change |
|------|--------|
| `factorio_mod_manager/ui/downloader_tab.py` | Full rewrite |

---

## Key Decisions

- **D-01**: `DownloaderTab(QWidget)` — not ttk.Frame
- **D-06/D-07**: All params stored in `__init__` before `start()` on all three workers
- **PREP-03 fixed**: `download_btn.setEnabled(True)` called unconditionally in `_on_download_finished` (re-enables on error)
- **T-05-02 mitigated**: `html_lib.escape(message)` applied before embedding in `<span>` in `_append_console`

---

## Workers Created

| Class | Base | Signals |
|-------|------|---------|
| `DownloadWorker` | `QThread` | `progress(int,int)`, `mod_status(str,str)`, `log_message(str,str)`, `finished(bool,list)` |
| `ResolveWorker` | `QThread` | `resolved(dict)`, `error(str)` |
| `SearchWorker` | `QThread` | `result(dict)`, `error(str)` |

---

## DownloaderTab Layout

```
QVBoxLayout (16px margins):
  URL row:      QLineEdit + QPushButton "Load Mod"
  Info label:   (mod title/author shown after resolve)
  Folder row:   QLabel + QLineEdit(readOnly) + QPushButton "Browse"
  Options row:  QCheckBox "Include optional dependencies"
  Download btn: QPushButton (objectName="accentButton", full-width)
  Progress:
    Left col:   QProgressBar + QTextEdit console
    Right:      QScrollArea (fixedWidth=220) — per-mod sidebar
```

---

## Behavior Parity

- 500ms debounce on URL field (`QTimer.setSingleShot(True).setInterval(500)`)
- Per-mod sidebar clears on each new download start
- Progress bar resets + re-polishes QSS on each start
- Config persistence: `config.get/set("mods_folder")`
- Offline check before download start
- Toast notifications: empty URL, no folder, offline, success, failure
- Status bar via `StatusManager.push_status()` on each progress tick
