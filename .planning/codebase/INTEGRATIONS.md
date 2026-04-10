# External Integrations

**Analysis Date:** 2026-04-10

## APIs & External Services

### Factorio Mod Portal — Metadata API

- **Base URL:** `https://mods.factorio.com`
- **API base:** `https://mods.factorio.com/api/mods`
- **Implementation:** `factorio_mod_manager/core/portal.py` — `FactorioPortalAPI` class
- **SDK/Client:** `requests.Session` (though auth on the Session is never exercised — see Authentication section)
- **Auth required:** None — all endpoints used are public
- **Request timeout:** 10 seconds (all `session.get(..., timeout=10)` calls)

**Endpoints used:**

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/api/mods/{name}/full` | Fetch complete mod info including releases, dependencies, download count |
| GET | `/api/mods?q={query}` | Search mods by name (returns up to N results, limit applied client-side) |
| GET | `/mod/{name}/changelog` | Scrape HTML changelog page (parsed with BeautifulSoup + `html.parser`) |

**Search behaviour:**
- Mod search is debounced 500ms in the UI (`factorio_mod_manager/ui/downloader_tab.py` line 902: `self.parent.after(500, self._search_mod)`) before the API call fires

**Error classification** (`PortalAPIError.error_type`):
- `"offline"` — `ConnectionError` (DNS/network failure)
- `"timeout"` — `requests.Timeout`
- `"not_found"` — HTTP 404
- `"server_error"` — HTTP 500/502/503/504
- `"unknown"` — any other exception

---

### re146.dev Mod Mirror — File Downloads

- **Base URL:** `https://mods-storage.re146.dev`
- **URL pattern:** `https://mods-storage.re146.dev/{mod_name}/{version}.zip`
- **Implementation:** `factorio_mod_manager/core/downloader.py` — `_download_with_re146()`
- **Auth required:** None — public mirror, no credentials
- **HTTP client:** Plain `requests.get(mirror_url, timeout=60, stream=True)` — does **not** use the `FactorioPortalAPI` session
- **Download timeout:** 60 seconds
- **Concurrency:** Up to `max_workers` parallel downloads (default 4) via `ThreadPoolExecutor`

**Download flow:**
1. Construct URL: `https://mods-storage.re146.dev/{name}/{version}.zip`
2. Streaming GET with 8192-byte chunks; logs progress for large files
3. Write chunks to `{mods_folder}/{name}_{version}.zip`
4. Validate downloaded file is a valid ZIP (`zipfile.ZipFile.testzip()`)
5. Delete file on validation failure

**Note:** `get_mod_download_url()` in `portal.py` constructs a `https://mods.factorio.com/download/...` URL from portal metadata, but this method is **never called** by the download pipeline. All actual downloads go through `_download_with_re146()` using the re146.dev mirror.

---

## Data Storage

**Config file:**
- Path: `~/.factorio_mod_manager/config.json`
- Managed by: `factorio_mod_manager/utils/config.py` — `Config` class
- Created on first run with defaults if absent
- Read on startup; written on every `Config.set()` call

**Config keys:**
```json
{
  "mods_folder":        "path/to/Factorio/mods",
  "username":           null,
  "token":              null,
  "theme":              "dark",
  "auto_backup":        true,
  "download_optional":  false,
  "auto_refresh":       true,
  "max_workers":        4
}
```

**Mod files:**
- Stored as `.zip` files in the user-configured mods folder
- Default locations auto-detected by `Config._detect_factorio_folder()`:
  - Windows: `%APPDATA%\Factorio\mods`
  - Linux: `~/.factorio/mods`
  - macOS: `~/Library/Application Support/factorio/mods`
- Mod metadata read from `info.json` inside each `.zip` via `factorio_mod_manager/utils/helpers.py` — `parse_mod_info()`

**Caching:**
- None — portal metadata is fetched fresh on every scan/check

---

## Authentication & Identity

**IMPORTANT — credentials are dead code:**

`username` and `token` are stored in `config.json` and accepted as constructor arguments by both `FactorioPortalAPI` and `ModDownloader`. When both are present, `self.session.auth = (username, token)` is set on the `requests.Session`. However:

1. The Session is only used for portal metadata calls (`/api/mods/...`) — which are **public endpoints requiring no auth**.
2. All actual mod downloads bypass the Session entirely and use plain `requests.get()` against the re146.dev mirror — also a **public endpoint requiring no auth**.
3. `get_mod_download_url()` (which constructs a credentialled `mods.factorio.com/download/...` URL) is **never invoked** in the download pipeline.

**Result:** No authenticated request is ever made. `username` and `token` in `config.json` have no functional effect on any operation the application currently performs.

---

## Monitoring & Observability

**Error tracking:**
- None — no external service (Sentry, Datadog, etc.)
- Exceptions are caught, classified, and surfaced to the UI via callback strings

**Logs:**
- UI log viewer: `factorio_mod_manager/ui/logger_tab.py`
  - Polls a Queue every 100ms (`self.frame.after(100, self._poll_logs)`) to display log messages in real time
- Application logger: `factorio_mod_manager/utils/logger.py`
- Log file location: `~/.factorio_mod_manager/logs/app.log`

---

## CI/CD & Deployment

**Hosting:** No cloud backend. The application is a standalone desktop client.

**Build pipeline (manual, local):**
1. PyInstaller bundles `factorio_mod_manager/main.py` → `FactorioModManager.exe` using `FactorioModManager.spec`
2. Inno Setup packages the executable into a Windows installer using `FactorioModManager.iss`
3. Distribution: GitHub Releases (manual upload)

**No CI/CD pipeline detected.**

---

## Webhooks & Callbacks

**Incoming:** None — no server component.

**Outgoing:** None — all HTTP calls are outbound GET requests initiated by user action.

---

*Integration audit: 2026-04-10*
