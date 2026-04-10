# Features & User-Facing Behavior

**Analysis Date:** 2026-04-10
**Source:** Direct code analysis of `factorio_mod_manager/ui/`, `factorio_mod_manager/core/`

---

## Application Startup

1. `main.py` runs: configures Windows DPI awareness, initializes file + queue logging.
2. A `Queue` is created and passed to both the logger and the UI so log lines flow into the **Logs tab** in real time.
3. Tkinter root window opens **maximized** (1100×750 minimum, starts zoomed).
4. `MainWindow` builds:
   - **Dark header** (`#1a1a1a`) with title "🏭 Factorio Mod Manager v1.1.0" and subtitle.
   - Blue accent separator line.
   - Tab notebook with three tabs: **⬇️ Downloader**, **✓ Checker & Updates**, **📋 Logs**.
   - **Status bar** at the bottom — shows live status messages from whichever tab is active.
5. `StatusManager` starts polling a queue every 100 ms; background threads push status strings into it, and it updates the status bar on the Tk main thread.
6. Mods folder is **auto-populated** from `~/.factorio_mod_manager/config.json` in both tabs.

---

## Tab 1 — ⬇️ Downloader

**Purpose:** Find, preview, and download a Factorio mod (and all its dependencies) into the local mods folder.

### Layout

The tab is a **single vertically-scrollable page** divided into sections:

| Section | Contents |
|---|---|
| **Download Mod** | Mod URL/name input + "Load Mod" button + Mods Folder picker |
| **Mod Information** | Read-only text panel showing metadata after lookup |
| **Options** | Checkbox: _Include optional dependencies_ |
| **Action buttons** | "Download" button |
| **Download Progress** | Overall progress bar + % label + console log (left) + per-mod sidebar (right) |

### Behaviors

#### Typing a mod URL (auto-search, debounced 500 ms)
- User types into the URL field (placeholder: `https://mods.factorio.com/mod/`).
- After 500 ms of inactivity, `_search_mod()` fires a **background thread**.
- The thread calls `FactorioPortalAPI.get_mod(mod_name)` — fetches **basic metadata only** (no dependency resolution, intentionally fast).
- **Mod Information** panel updates with: Title, Author, Download count, Latest version + release date, Homepage, GitHub link, Description, and the direct dependencies from `info_json`.
- Dependencies shown in four categories: Required, Optional, Incompatible, Expansions (Space Age / Elevated Rails etc.).
- If the mod is not found or the user is offline, an error message is shown in the panel.

#### Clicking "Load Mod"
- Runs `_load_dependencies_thread` in background.
- Calls `ModDownloader.resolve_dependencies()` with `include_optional=True` to display the **full recursive dependency tree** (not just direct deps).
- Cross-checks against installed mods: lists any conflicts (mods that are incompatible with the target and already installed).
- Result is displayed in the **Mod Information** panel with expanded dependency sections.

#### Browsing the mods folder
- "Browse" button opens a native OS folder picker.
- Selection is saved immediately to both the UI variable and `config.json`.

#### Clicking "Download"
- Validates: URL not empty, mods folder set, network online.
- If `url` does not contain `/mod/`, treats the whole entry as a mod name directly.
- Disables the Download button for the duration.
- Clears the progress console and the per-mod sidebar.
- Starts `_download_thread` in background:
  1. Creates `ModDownloader(mods_folder, username, token)`.
  2. Hooks three callbacks: `set_progress_callback` (console text), `set_overall_progress_callback` (progress bar + status bar), `set_mod_progress_callback` (per-mod sidebar items).
  3. Calls `ModDownloader.download_mods([mod_name], include_optional=<checkbox>)`.
  4. Dependency resolution happens recursively inside the downloader (up to `max_workers=4` concurrent threads).
  5. Each mod shows its own row in the **Downloads sidebar** (right side of progress section) with a status label that transitions: "Preparing..." → "Downloading..." → "✓ Downloaded" (green) or "✗ Failed" (red).
  6. The main progress bar advances as mods complete: `completed/total * 100%`.
  7. Status bar shows: "Downloading: 2/5 mods (40%)".
- On success: green toast notification "✓ Successfully downloaded N mod(s)".
- On failure: red toast notification listing failed mods.
- On `PortalAPIError` (offline, not found, server error): specific error message in notification + console.
- Download button re-enabled in `finally` block.

#### Progress console (left side of progress section)
- Monospaced `Consolas` font, dark background.
- Tagged lines: blue (info), green (success), red (error), yellow (warning).
- Auto-scrolls to the latest message.

#### Per-mod downloads sidebar (right side of progress section)
- Scrollable list, one row per mod being downloaded.
- Each row: mod name (bold) + status label.
- Completed rows turn green or red.

---

## Tab 2 — ✓ Checker & Updates

**Purpose:** Scan the local mods folder, check versions against the portal, and manage (update / delete / backup) installed mods.

### Layout — Three-column grid

| Column | Contents |
|---|---|
| **Left sidebar** (220 px fixed) | ⚙️ Settings (folder picker + status indicator) + Action buttons (vertical stack) |
| **Center** (expandable) | 📦 Installed Mods list |
| **Right sidebar** (280 px fixed) | 📊 Statistics + 🔎 Search + Status filter buttons + Sort radio buttons |
| **Bottom bar** (spans all columns) | 📝 Operation Log |

### Left sidebar — Action buttons

| Button | Color | Enabled | Action |
|---|---|---|---|
| 🔍 Scan | Blue | Always | Scan local `.zip` files and fetch portal data |
| ⬆️ Check Updates | Yellow | After scan | Re-check portal for newer versions |
| 📥 Update Selected | Green | When ≥1 mod selected | Download updates for selected mods |
| 🗑️ Delete | Red | When ≥1 mod selected | Delete selected mod `.zip` files |
| 📥 Update All | Green | After scan | Update every outdated mod at once |
| 🧹 Backups | Brown | Always | Delete the entire `backup/` sub-folder |
| 💾 Backup | Purple | When ≥1 mod selected | Copy selected `.zip` files to `mods/backup/` |
| ℹ️ View Details | Blue | When exactly 1 selected | Open full-detail popup for that mod |

### Center — Installed Mods list

Each mod row (grid layout) shows:
- **☐ checkbox** (click to toggle selection; supports Ctrl+click for multi-select)
- **Name** — display title + internal mod name below it
- **Status** — color-coded: ✓ Up to date (green), ⬆️ Outdated (yellow), ❓ Unknown (gray), ✗ Error (red)
- **Version** — `installed_version → latest_version`
- **Author** — `by <name>`
- **Downloads** — numeric with thousands separator

Clicking a row or checkbox selects/deselects. Ctrl+click accumulates selection. Selected rows highlight dark green with "☑" indicator and raised border.

### Right sidebar — Statistics

After scan, shows a two-column label/value table:

- Total mods loaded
- Up to date count
- Outdated count
- Unknown / error count
- Total download count (sum across all mods)
- (populated by `CheckerPresenter.get_statistics()` / `format_statistics_multiline()`)

### Right sidebar — Search & Filters

- **Search box** — live filter by mod name (case-insensitive, on every keystroke via `trace("w")`).
- **Status filter buttons** — All / Outdated / Up to Date / Selected (2×2 grid).
- **Sort radio buttons** — Name / Version / Downloads / Date.
- Changing any filter re-renders the center list immediately via `_filter_mods()`.
- List scrolls to top on every filter change.

### Bottom bar — Operation Log

- Monospaced Consolas log, spans all 3 columns, color-coded by tag.
- All background operations (`[SCAN]`, `[CHECK]`, `[UPDATE]`, `[DELETE]`, `[BACKUP]`, `[CLEANUP]`) write here.
- Dual-writes: also goes to Python `logging` so it appears in the **Logs tab** and the log file.

### Behaviors

#### Auto-scan on tab open
- When the Checker tab becomes visible and no mods are loaded, a **3-second timer** fires `_start_scan()` automatically.
- Prevents duplicate auto-scans if the tab is briefly hidden and shown again.

#### Scanning (🔍 Scan)
1. Network connectivity check — aborts with warning notification if offline.
2. `ModChecker.scan_mods()` reads every `*.zip` in the mods folder, opens each ZIP, reads `info.json` inside, parses name/version/title/author/dependencies.
3. Concurrently fetches latest version + download count from Factorio portal for each mod.
4. Updates center list and statistics.
5. Toast: "✓ Scan complete! Found N mod(s) with latest information."
6. Re-enables all action buttons.
7. Scan/Check/Update/Update All buttons are all disabled during the scan.

#### Check Updates (⬆️ Check Updates)
- Requires a prior scan.
- Calls `CheckerLogic.check_updates()` which calls `ModChecker.check_updates()`.
- Only re-fetches from portal if data is stale (cache freshness logic in `ModChecker`).
- If data was fresh: "✓ Data is fresh. No refresh needed."
- If refreshed: "✓ Check finished. N update(s) available."
- Re-renders list and statistics.

#### Update Selected / Update All
- Update Selected requires at least one checkbox selected.
- Update All finds all mods with `ModStatus.OUTDATED` automatically.
- Both call `CheckerLogic.update_mods(mod_names)` which delegates to `ModDownloader`.
- Progress logged to the operation log.
- Toast: "✓ Updated N mod(s)" (with count of failures if any).

#### Delete
- Requires at least one selection.
- Shows a **persistent warning notification** with "Delete" and "Cancel" action buttons (does not auto-dismiss).
- On confirmation: `CheckerLogic.delete_mods()` removes `.zip` files from disk, updates in-memory mods dict.
- List and stats refreshed. Toast with result.

#### Backup
- Copies selected `.zip` files into `<mods_folder>/backup/`.
- Creates the `backup/` sub-folder if it does not exist.
- Per-mod logging, toast with count and failure summary.

#### Clean Backups (🧹 Backups)
- Calculates total size of `<mods_folder>/backup/`.
- Shows persistent confirmation notification with size: "Delete backup folder? (X.XX MB) This cannot be undone!"
- On confirmation: recursively deletes the entire `backup/` folder.
- Toast: "✓ Backup deleted - Freed X.XX MB".

#### View Details (ℹ️ View Details) — Popup window
- Only available when **exactly one** mod is selected.
- Opens a centered `1000×800` Toplevel popup on top of the main window.
- Popup is fully scrollable.
- Content (verified from source): detailed mod metadata formatted from the `Mod` dataclass — name, title, author, installed version, latest version, status, download count, and whatever other fields were fetched from the portal.

---

## Tab 3 — 📋 Logs

**Purpose:** Real-time display of all Python log output from all parts of the application.

### Layout

Full-width scrollable text area (dark background, `Courier` font, monospace).

### Behavior

- Polls the shared `Queue` every **100 ms** via `frame.after(100, ...)`.
- Drains all available messages from the queue each poll cycle.
- Classifies log level from the message text (contains `" - ERROR - "`, `" - WARNING - "`, etc.).
- Inserts with color tag: ERROR red, WARNING yellow, DEBUG gray, INFO gray.
- Auto-scrolls to the latest entry.
- There is no clear button exposed in the UI (code has a `clear_logs()` method but it is not wired to a button).

---

## Notifications System

A `NotificationManager` overlays toast messages on top of all tab content (rendered on the root window, not per-tab).

- **Toast types:** success (green), error (red), warning (yellow), info (blue).
- **Duration:** 4000 ms default; 5000–6000 ms for download/scan results; `0` = persistent (used for confirmations).
- **Action buttons:** Persistent notifications can include inline buttons (e.g., "Delete" + "Cancel" for destructive actions).
- Notifications stack vertically if multiple appear simultaneously.

---

## Status Bar

- Lives at the bottom of the main window.
- Fed by `StatusManager` from a queue — background threads call `status_manager.push_status(msg, type)`.
- Types map to colors: `"working"` = blue animated, `"success"` = green, `"error"` = red, `"info"` = default.
- Both tabs push status: the most recent operation wins.

---

## Configuration & Settings Persistence

All user settings are stored in `~/.factorio_mod_manager/config.json` and survive restarts.

| Key | Where it's set | Default |
|---|---|---|
| `mods_folder` | Browse button (both tabs) | Auto-detected Factorio mods path |
| `username` | Stored in config (currently unused — see note below) | `""` |
| `token` | Stored in config (currently unused — see note below) | `""` |
| `download_optional` | "Include optional dependencies" checkbox in Downloader tab | `false` |
| `theme` | Not currently in UI | `"dark"` |
| `auto_backup` | Not currently in UI | `true` |
| `auto_refresh` | Not currently in UI | `true` |
| `max_workers` | Not currently in UI | `4` |

> **Note on credentials:** `username` and `token` are accepted by `ModDownloader.__init__` and `FactorioPortalAPI.__init__`, and an authenticated `requests.Session` is constructed — but it is **never used**. All actual downloads go through the public `re146.dev` mirror (`https://mods-storage.re146.dev/{name}/{version}.zip`) via plain `requests.get()`, bypassing the session entirely. All metadata API calls (`/api/mods/{name}/full`) are also public endpoints. Credentials are effectively dead code in the current implementation — no credential input UI is needed.

---

## What Is NOT Currently in the UI

| Missing feature | Notes |
|---|---|
| Theme toggle | Dark theme only; no light mode toggle |
| Settings tab / preferences panel | No dedicated settings screen |
| Clear log button | `LoggerTab.clear_logs()` exists but is not exposed |
| Mod search/browse from portal | Only direct URL/name input; no browse-by-category |
| Automatic app updates | No self-update mechanism |
| Mod enable/disable toggle | No `.compat` disable file management |
| Per-mod changelog display | Not shown in the Details popup currently |

---

*Features analysis: 2026-04-10*
