# Behavioral Parity Checklist — Phase 1 Qt Migration

> Used by: Phase 1 (Qt Platform Migration) to verify behavioral parity before marking Phase 1 complete.
> Source: `.planning/codebase/FEATURES.md` (analysis date: 2026-04-10)
> Generated: 2026-04-10

Each item is checkable when verified manually in the Qt application.
Items marked **(PREP-03 fix)** and **(PREP-04 fix)** are behaviors added in Phase 0 that must also be present in Qt.

---

## Application Startup

- [ ] App window launches maximized (zoom/maximize state on open)
- [ ] Minimum window size is 1100×750 (cannot shrink below this)
- [ ] Header shows title "Factorio Mod Manager" (or "🏭 Factorio Mod Manager v1.1.0") with subtitle text
- [ ] A blue accent separator line is visible below the header
- [ ] Three tabs are visible: Downloader (or "⬇️ Downloader"), Checker & Updates (or "✓ Checker & Updates"), Logs (or "📋 Logs")
- [ ] Status bar is visible at the bottom of the main window
- [ ] Mods folder input in Downloader tab is auto-populated from saved config on launch
- [ ] Mods folder input in Checker tab is auto-populated from saved config on launch

---

## Tab 1 — Downloader

### Layout

- [ ] Mod URL/name input field is present with placeholder text containing "mods.factorio.com/mod/"
- [ ] "Load Mod" button is present next to or near the URL input
- [ ] Mods Folder display field is present with a "Browse" button
- [ ] "Include optional dependencies" checkbox is present
- [ ] "Download" button is present
- [ ] Download Progress section is present with a progress bar and a progress console log area
- [ ] Per-mod sidebar is present to the right of the progress console

### Typing in URL field — debounced search

- [ ] Typing in the URL field does NOT immediately trigger a mod search (no search on every keystroke)
- [ ] After approximately 500 ms of inactivity in the URL field, a background mod lookup fires
- [ ] Mod Information panel updates with: Title, Author, Download count, Latest version, Release date, Description, and Dependencies after the lookup completes
- [ ] Dependencies are categorized as: Required, Optional, Incompatible, Expansions
- [ ] If mod is not found, an error message is shown in the Mod Information panel
- [ ] If the user is offline during auto-search, an error message is shown in the Mod Information panel

### "Load Mod" button

- [ ] Clicking "Load Mod" triggers full recursive dependency resolution (not just direct deps)
- [ ] Resolution results show the complete dependency tree with Required, Optional, Incompatible, Expansions sections
- [ ] Conflicts with installed mods (incompatible mods already present) are listed in the Mod Information panel

### Browse mods folder

- [ ] Clicking "Browse" opens a native OS folder picker dialog
- [ ] After selecting a folder, the path appears in the Mods Folder field
- [ ] The selected folder path persists on next app launch (saved to config)

### Download button

- [ ] Clicking "Download" with empty URL shows an error notification
- [ ] Clicking "Download" with no mods folder selected shows an error notification
- [ ] Clicking "Download" while offline shows an error notification **(PREP-03 fix)**: Download button re-enables immediately after this error so user can retry without restarting
- [ ] Download button is disabled for the duration of a successful download start
- [ ] Progress console clears at the start of each new download
- [ ] Per-mod sidebar clears at the start of each new download

### Download in progress

- [ ] Progress bar is visible and advances as mods complete (e.g., 2/5 → 40%)
- [ ] Status bar shows download progress text (e.g., "Downloading: 2/5 mods (40%)")
- [ ] Per-mod sidebar shows one row per mod being downloaded
- [ ] Each sidebar row transitions: "Preparing..." → "Downloading..." → "✓ Downloaded" (green) or "✗ Failed" (red)
- [ ] Progress console shows color-coded log lines: info = blue, success = green, error = red, warning = yellow
- [ ] Progress console auto-scrolls to the latest message

### Download results

- [ ] Successful download shows a green toast notification such as "✓ Successfully downloaded N mod(s)"
- [ ] Failed download shows a red toast notification listing the failed mods
- [ ] A `PortalAPIError` (offline, not found, server error) shows a specific error message in both the notification and console
- [ ] Download button re-enables after completion (success or failure)

---

## Tab 2 — Checker & Updates

### Layout

- [ ] Three-column layout: left sidebar (~220 px), center mod list (expandable), right sidebar (~280 px)
- [ ] Left sidebar contains: mods folder picker with status indicator + action buttons in a vertical stack
- [ ] Center shows an installed mods list with columns: checkbox, name, status, version, author, downloads
- [ ] Right sidebar shows: statistics panel + search box + status filter buttons + sort radio buttons
- [ ] An operation log spans the full width at the bottom of the tab

### Action buttons

- [ ] "Scan" (🔍) button is always visible and clickable
- [ ] "Check Updates" (⬆️) button is present
- [ ] "Update Selected" (📥) button is present
- [ ] "Delete" (🗑️) button is present
- [ ] "Update All" button is present
- [ ] "Backups" (🧹 Clean Backups) button is present
- [ ] "Backup" (💾) button is present
- [ ] "View Details" (ℹ️) button is present

### Auto-scan behavior

- [ ] When the Checker tab is opened for the first time (no mods loaded), a scan starts automatically after ~3 seconds
- [ ] If the tab is briefly hidden and reshown, a duplicate auto-scan does NOT fire

### Scan operation

- [ ] Clicking "Scan" reads all `*.zip` files from the mods folder
- [ ] Each mod row shows: name, status (✓ / ⬆️ / ❓ / ✗), installed version → latest version, author, download count
- [ ] Statistics panel updates after scan: total mods, up to date count, outdated count, unknown/error count, total downloads
- [ ] Success toast appears: "✓ Scan complete! Found N mod(s) with latest information."
- [ ] If offline during scan, a warning notification is shown and scan is aborted

### Mod selection

- [ ] Clicking a row or its checkbox selects/deselects that mod
- [ ] Ctrl+click accumulates selection (multi-select)
- [ ] Selected rows highlight visually (e.g., green background with "☑" indicator)

### Check Updates

- [ ] "Check Updates" re-fetches portal data for installed mods
- [ ] If data is already fresh, shows: "✓ Data is fresh. No refresh needed."
- [ ] If data is refreshed, shows: "✓ Check finished. N update(s) available."
- [ ] Mod list and statistics re-render after check

### Update Selected / Update All

- [ ] "Update Selected" requires at least one mod checkbox to be selected; clicking with none selected has no effect (or shows an informational message)
- [ ] "Update All" finds all outdated mods automatically without requiring checkboxes
- [ ] Both operations log progress to the operation log at the bottom
- [ ] Toast appears on completion: "✓ Updated N mod(s)" (with failure count if any)

### Delete

- [ ] "Delete" requires at least one mod selected
- [ ] Clicking "Delete" shows a **persistent** confirmation notification (does NOT auto-dismiss) with "Delete" and "Cancel" buttons
- [ ] Confirming deletes the `.zip` file(s) from disk
- [ ] Cancelling takes no action
- [ ] Mod list and statistics update after delete

### Backup

- [ ] "Backup" copies selected `.zip` files to `<mods_folder>/backup/`
- [ ] `backup/` subfolder is created if it does not exist
- [ ] Toast appears with count and failure summary

### Clean Backups

- [ ] "Backups" button calculates total size of `<mods_folder>/backup/`
- [ ] Shows a **persistent** confirmation notification with size: e.g., "Delete backup folder? (X.XX MB) This cannot be undone!"
- [ ] Confirming deletes the entire `backup/` folder recursively
- [ ] Toast appears: "✓ Backup deleted - Freed X.XX MB"

### View Details popup

- [ ] "View Details" is only enabled when exactly one mod is selected (disabled otherwise)
- [ ] Clicking opens a popup window (approximately 1000×800, centered over main window)
- [ ] Popup is scrollable
- [ ] Popup displays detailed metadata: name, title, author, installed version, latest version, status, download count

### Search and filter (right sidebar)

- [ ] Search box filters the mod list live on every keystroke (case-insensitive)
- [ ] "All" status filter button shows all mods
- [ ] "Outdated" filter shows only outdated mods
- [ ] "Up to Date" filter shows only up-to-date mods
- [ ] "Selected" filter shows only currently selected mods
- [ ] Sort by "Name" re-orders list alphabetically immediately
- [ ] Sort by "Version" re-orders by version immediately
- [ ] Sort by "Downloads" re-orders by download count immediately
- [ ] Sort by "Date" re-orders by date immediately
- [ ] Changing any filter or sort scrolls the list back to the top

---

## Tab 3 — Logs

- [ ] Tab shows a full-width scrollable log display area
- [ ] Log entries from Downloader tab operations appear in the Logs tab
- [ ] Log entries from Checker tab operations appear in the Logs tab
- [ ] ERROR lines are displayed in red
- [ ] WARNING lines are displayed in yellow
- [ ] DEBUG lines are displayed in gray
- [ ] INFO lines are displayed in gray
- [ ] Log display auto-scrolls to the latest entry
- [ ] **Clear button is present** **(PREP-04 fix)**: clicking it clears all entries from the log display

---

## Notifications System

- [ ] Success notifications appear in green and auto-dismiss after ~4000 ms
- [ ] Error notifications appear in red and auto-dismiss
- [ ] Warning notifications appear in yellow and auto-dismiss
- [ ] Persistent notifications (for Delete and Clean Backups confirmations) do NOT auto-dismiss
- [ ] Persistent notifications include inline action buttons (e.g., "Delete" + "Cancel")
- [ ] Multiple notifications stack vertically when triggered simultaneously

---

## Status Bar

- [ ] Status bar updates during active operations (shows progress text)
- [ ] "Working" state shows progress text in blue (or animated)
- [ ] "Success" state shows completion message in green
- [ ] "Error" state shows error message in red
- [ ] Status bar reflects activity from both the Downloader and Checker tabs

---

## Configuration Persistence

- [ ] `mods_folder` path survives app restart (auto-populated on next launch)
- [ ] "Include optional dependencies" checkbox state (`download_optional`) survives app restart
- [ ] No credential input UI is needed (username/token are handled internally and not user-facing)

---

## Behaviors NOT to Replicate (Tkinter bugs — leave behind in Qt)

The following are known Tkinter defects that must NOT be carried over to the Qt implementation:

- [ ] CONFIRMED ABSENT: No direct widget mutation from background threads (Tkinter bug — Qt MUST use signals/slots or thread-safe queue dispatching instead)
- [ ] CONFIRMED ABSENT: No bare `except:` or `except Exception:` blocks that silently swallow errors — Qt code must propagate or log errors explicitly

---

*Generated: 2026-04-10*
*Source: .planning/codebase/FEATURES.md*
*Used by: Phase 1 (Qt Platform Migration) to verify behavior parity before Phase 1 completion*
