# Phase 3: Search, Filtering, and Settings — Research

**Phase:** 03-search-filter-settings
**Date:** 2026-04-11
**Requirements:** SRCH-01, SRCH-02, SRCH-03, SETT-01, SETT-02, SETT-03

---

## RESEARCH COMPLETE

---

## 1. Standard Stack (confirmed from codebase audit)

| Concern | Library / Approach | Source |
|---------|-------------------|--------|
| Widgets | PySide6 built-ins — QDialog, QFrame, QComboBox, QSpinBox, QScrollArea, QFormLayout, QGroupBox | new for Phase 3 |
| Popup overlay | `QFrame` with `Qt.WindowType.Popup` | PySide6 standard for transient dropdowns |
| Keyboard shortcut | `QShortcut(QKeySequence("Ctrl+K"), parent)` | PySide6 standard |
| Theme switching | QSS file swap via `QApplication.instance().setStyleSheet()` | extends existing `load_stylesheet()` system |
| OS theme detection | `QApplication.instance().styleHints().colorScheme()` → `Qt.ColorScheme` | PySide6 6.5+ |
| System theme change | `QApplication.instance().paletteChanged` signal | fires on OS dark/light switch |
| Debounce | `QTimer.setSingleShot(True) + setInterval(200)` | established pattern in `SearchWorker` (500ms) |
| Threading | `QThread` + typed `Signal`/`Slot` | existing project pattern |
| No new packages | All from PySide6 + stdlib | confirmed — pyproject.toml unchanged |

---

## 2. Architecture Patterns

### 2.1 QSS Template System — Extension Approach

`factorio_mod_manager/ui/styles/__init__.py` `load_stylesheet()` reads `dark_theme.qss`, calls `str.format_map(token_map)` where `token_map = {k: str(v) for k, v in vars(tokens).items()}`. Format keys are `{TOKEN_NAME}` in the QSS file (single braces — QSS parser does not use braces, so no escaping needed).

**Phase 3 extension plan:**
1. Add `LIGHT_*` token constants to `tokens.py` (same module, appended at end).
2. Create `light_theme.qss` mirroring `dark_theme.qss` structure, substituting each dark token reference with its `LIGHT_` equivalent (e.g., `{BG_PRIMARY}` → `{LIGHT_BG_PRIMARY}`).
3. Add `load_and_apply_theme(theme: str, app=None)` to `styles/__init__.py` that selects the correct QSS file based on `theme` value, resolves the token map, and calls `app.setStyleSheet(result)`.
4. Append Phase 3 QSS selectors to `dark_theme.qss` only (single source of truth for dark theme). Light equivalents go in `light_theme.qss`.

**New selectors needed in dark_theme.qss (not yet present):**
- `QComboBox` / `QComboBox::drop-down` / `QComboBox QAbstractItemView`
- `QSpinBox` / `QSpinBox::up-button` / `QSpinBox::down-button`
- `QLineEdit#globalSearchBar` / `:focus` override
- `QPushButton#categoryChip` / `:hover` / `[selected="true"]`
- `QPushButton#settingsButton` (transparent, icon-only, hover ring)
- `QScrollArea` / `QScrollArea > QWidget > QWidget` (transparent bg for settings scroll area)

**Existing in dark_theme.qss (do NOT duplicate):**
- `QGroupBox` / `QGroupBox::title` ✓
- `QLineEdit` base / `:focus` / `:read-only` ✓
- `QPushButton` base / `#accentButton` / `#destructiveButton` ✓
- `QCheckBox` / `QRadioButton` ✓

### 2.2 Theme Switching — `load_and_apply_theme()`

```python
def load_and_apply_theme(theme: str, app=None) -> None:
    if theme == "system":
        app_instance = app or QApplication.instance()
        scheme = app_instance.styleHints().colorScheme()
        theme = "light" if scheme == Qt.ColorScheme.Light else "dark"
    qss_filename = "light_theme.qss" if theme == "light" else "dark_theme.qss"
    qss_path = Path(__file__).parent / qss_filename
    template = qss_path.read_text(encoding="utf-8")
    token_map = {k: str(v) for k, v in vars(tokens).items() if not k.startswith("_")}
    result = template.format_map(token_map)
    target = app or QApplication.instance()
    if target:
        target.setStyleSheet(result)
```

System theme auto-switch (D-18): `QApplication.instance().paletteChanged.connect(self._on_palette_changed)` in `MainWindow.__init__`. Handler reads `config.get("theme")` — if "system", calls `load_and_apply_theme("system")`.

### 2.3 Filter/Sort Extraction — `FilterSortBar`

Existing checker tab right sidebar holds inline `QLineEdit` (search_edit), `QGroupBox("Filter")` with checkable `QPushButton` filter buttons (`self._filter_btns`), and `QGroupBox("Sort by")` with `QRadioButton` sort radios (`self._sort_radios`). These get replaced by a `FilterSortBar(QWidget)` instance.

`CheckerPresenter.filter_mods(mods, search_query, filter_mode, selected_mods, sort_by)` signature stays unchanged. `FilterSortBar.filter_changed` signal maps to the same parameters via `_on_filter_bar_changed(query, status, sort_by, priority)` in `CheckerTab`.

Key: remove `_on_search_changed`, `_on_filter_changed`, `_on_sort_changed` methods replacing with single `_on_filter_bar_changed`. Keep `self._search_query`, `self._current_filter`, `self._current_sort` instance state (used by `_populate_table`).

### 2.4 Category Chips + Portal Category Query

`FactorioPortalAPI.search_mods()` currently: `GET /api/mods?q={query}&page_size={limit}`. Portal API accepts `?tag={category}` for category filtering. Adding `category: str = ""` param: when non-empty, inject `"tag": category` into params dict.

No API exists for listing portal categories programmatically. Use hardcoded known tag list: `["All", "combat", "logistics", "trains", "mining", "energy", "environment", "cheats", "circuit-network", "library", "big-mods"]`.

`CategoryChipsBar` chip click → new `CategoryBrowseWorker(QThread)` in DownloaderTab → calls `portal.search_mods("", limit=20, category=chip_name)` → populates existing `self.search_results_list`. `"All"` chip → `portal.search_mods("", limit=20, category="")` (returns trending/recent with no filter).

### 2.5 QFrame Popup for Search Results

```python
popup = QFrame(main_window, Qt.WindowType.Popup)
popup.move(search_bar.mapToGlobal(QPoint(0, search_bar.height())))
popup.show()
```

Close triggers: `focusOutEvent`, Escape via `keyPressEvent`, result selection. `QFrame` with `Popup` window type auto-closes on click outside. Size: fixed 400px wide, dynamic height (max 480px with `QScrollArea`).

Result rows: `QPushButton` with flat style + hover using existing `BTN_HOVER_BG` pattern.

Keyboard navigation: track `self._focused_row: int` index; `↑`/`↓` shift focus; `Enter` emits `result_selected(mod_name, source)`.

### 2.6 ModDetailsDialog

`QDialog(parent=main_window)` modal, `setMinimumSize(520, 400)`. Constructor: `ModDetailsDialog(data: dict | Mod, source: str, parent=None)`. Source-neutral: duck-typed access with `.get()` for dicts, `getattr` for Mod objects. Footer: `QPushButton("Close")` + context action button (label driven by `source` param: `"Update"` if source=`"installed"` + mod is outdated, `"Add to Queue"` otherwise).

### 2.7 MainWindow Header Utility Zone Injection

Current `_create_header()` title_row layout: `title_label → addStretch() → subtitle_label`.

Phase 3 target layout: `title_label → addStretch() → GlobalSearchBar → settingsButton`.

Action: remove `subtitle_label` from title_row (or demote to a separate row). Insert `GlobalSearchBar` then `QPushButton#settingsButton` between stretch and end of title_row. The subtitle can be omitted in Phase 3 (redundant with window title now visible in titlebar).

### 2.8 Settings Page — `QStackedWidget` Indexing

Current page indices:
- 0: DownloaderTab  
- 1: CheckerTab  
- 2: LoggerTab  
- 3: SettingsPage (new, Phase 3)

Nav rail adds `("⚙  Settings", 3)` to the `nav_items` list in `_create_nav_rail()`. `_create_pages()` adds `SettingsPage` at index 3. Header `#settingsButton` click navigates to index 3.

Unsaved-changes guard: `MainWindow` connects to each nav rail button's `toggled` signal. Before accepting a navigation away from index 3, checks `self.settings_page.has_unsaved_changes()` → if true, shows `QMessageBox.question(self, "Unsaved Changes", "Save before leaving?", Save | Discard | Cancel)`.

### 2.9 CheckerTab — mods_loaded Signal for Global Search

`CheckerTab` needs to expose a public `mods_loaded = Signal(object)` class-level signal. Emit it from `_on_mods_loaded(mods)` after `self._mods = mods`. `MainWindow` connects this signal to `self._global_search_bar.set_installed_mods(mods)`.

---

## 3. Credential Removal Scope

**`Config.DEFAULTS`:** Remove `"username": None` and `"token": None`. In `Config.save()`, filter before write: `safe_data = {k: v for k, v in self.data.items() if k not in ("username", "token")}`. Use `safe_data` in `json.dump()`. Handles stale configs that still have these keys — they are silently dropped on next save.

**`FactorioPortalAPI.__init__(self)`:** Remove `username: Optional[str] = None, token: Optional[str] = None` params. Remove `self.username = username` and `self.token = token` body lines. Keep `self.session = requests.Session()` unchanged.

**Verify no active use:** `grep -r "username\|token" factorio_mod_manager/` should only return config.py defaults (removed) and portal.py constructor (removed). No download path uses auth — confirmed from codebase audit.

---

## 4. Don't Hand-Roll

| Pattern | Use Instead |
|---------|------------|
| Custom dropdown widget | `QFrame(parent, Qt.WindowType.Popup)` — Qt manages focus/dismiss |
| Manual OS theme polling | `QApplication.paletteChanged` signal — OS fires it |
| Manual form layout | `QFormLayout` inside `QGroupBox` — handles label/field alignment |
| Custom file browse | `QFileDialog.getExistingDirectory()` — already used in `CheckerTab._on_browse()` |
| Custom debounce timer | `QTimer.setSingleShot(True)` — already patterned in `DownloaderTab` |
| Category API discovery | Hardcoded known tag list — no clean API endpoint for portal categories |

---

## 5. Common Pitfalls

1. **`QFrame(Popup)` parent**: Must be `main_window` (top-level), not the search bar widget. Popup anchored below the search bar via `mapToGlobal()`.
2. **Dynamic QSS property refresh**: After `setProperty("selected", True)`, must call `widget.style().unpolish(widget)` + `widget.style().polish(widget)` for Qt to re-evaluate QSS `[selected="true"]` selector.
3. **`format_map` vs `format`**: `str.format_map(token_map)` raises `KeyError` if any `{TOKEN}` in the QSS has no matching key. `light_theme.qss` must use only `{LIGHT_*}` prefixed tokens that exist in `tokens.py`.
4. **`QComboBox.currentIndexChanged` vs `currentTextChanged`**: Prefer `currentIndexChanged` — fires even on programmatic changes from `load_values()`. Disconnect during `load_values()` or guard with `blockSignals(True)` to prevent spurious live theme preview on page load.
5. **SettingsPage Save writes all keys**: `Config.set()` writes to file on every call. Prefer: collect all values from `get_values()`, call `config.set(k, v)` for each changed key, then `config.save()` once.
6. **CheckerTab right sidebar**: Replacing three inline control groups (search_edit, filter_group, sort_group) with FilterSortBar. Remove `self._filter_btns: Dict[str, QPushButton]` and `self._sort_radios: Dict[str, QRadioButton]` instance attribute declarations and all references including `_on_filter_changed(key)` and `_on_sort_changed(key)` and `_on_search_changed(text)` methods — these are superseded by `_on_filter_bar_changed`.
7. **`QScrollArea` background**: By default `QScrollArea` inherits `QFrame` background (`BG_PANEL`). Settings page content area looks wrong without setting `setWidgetResizable(True)` and targeting `QScrollArea > QWidget > QWidget { background: transparent; }` in QSS.

---

## 6. Validation Architecture

> Consumed by VALIDATION.md template for Nyquist dimension 8.

```yaml
validation_targets:
  - id: V-SRCH-01
    description: "Unified search bar appears in header; Ctrl+K focuses it; typing shows grouped popup with Installed/Portal sections"
    automated: "grep -r 'GlobalSearchBar\\|globalSearchBar' factorio_mod_manager/ui/"
    manual: "Launch app, press Ctrl+K, type 'base', verify popup appears with sections"
    
  - id: V-SRCH-02
    description: "FilterSortBar replaces right sidebar controls in CheckerTab; filter_changed signal drives _populate_table"
    automated: "grep -n 'FilterSortBar\\|filter_changed' factorio_mod_manager/ui/checker_tab.py"
    manual: "Type in filter box, change status combo, verify table updates without page reload"
    
  - id: V-SRCH-03
    description: "CategoryChipsBar visible in DownloaderTab; selecting a chip triggers portal search with category param"
    automated: "grep -n 'CategoryChipsBar\\|category_selected' factorio_mod_manager/ui/downloader_tab.py"
    manual: "Open Downloader, click 'trains' chip, verify search_results_list populates with train mods"
    
  - id: V-SETT-01
    description: "SettingsPage accessible from nav rail and gear button; Paths/Behavior/Appearance/Advanced sections present"
    automated: "grep -n 'SettingsPage' factorio_mod_manager/ui/main_window.py"
    manual: "Click Settings nav item, verify all four QGroupBox sections visible"
    
  - id: V-SETT-02
    description: "Theme combo shows Dark/Light/System; selecting Light immediately applies light theme; Cancel reverts"
    automated: "grep -n 'load_and_apply_theme\\|paletteChanged' factorio_mod_manager/ui/"
    manual: "Open Settings, select Light — app turns light. Click Cancel — app reverts to prior theme"
    
  - id: V-SETT-03
    description: "max_workers QSpinBox (1-16), auto_backup and auto_refresh QCheckBox present; Save writes to config.json"
    automated: "grep -n 'max_workers\\|auto_backup\\|auto_refresh' factorio_mod_manager/ui/settings_page.py"
    manual: "Change max_workers to 2, click Save, verify ~/.factorio_mod_manager/config.json has max_workers=2"
    
  - id: V-CRED
    description: "No username/token in Config.DEFAULTS or FactorioPortalAPI constructor"
    automated: "grep -n 'username.*None\\|token.*None' factorio_mod_manager/utils/config.py factorio_mod_manager/core/portal.py"
    check: "grep should find zero matches in DEFAULTS and PortalAPI init"
```

---

*Phase: 03-search-filter-settings*
*Research date: 2026-04-11*
