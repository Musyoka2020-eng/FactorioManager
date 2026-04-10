# External Integrations

**Analysis Date:** 2026-04-09

## APIs & External Services

**Factorio Mod Portal:**
- Service: Factorio Mod Portal (https://mods.factorio.com)
- What it's used for:
  - Search mods by name
  - Fetch mod metadata (title, author, description, version)
  - Retrieve dependency information (required, optional, incompatible)
  - Get mod download URLs
  - Check for mod updates
- SDK/Client: `requests` library (2.32.0)
- Implementation: `factorio_mod_manager/core/portal.py` - `FactorioPortalAPI` class
- Auth: Optional HTTP Basic Auth (username/password)
  - Credentials stored in `~/.factorio_mod_manager/config.json`
  - Used for downloading mods when authentication required
- API Details:
  - Base URL: `https://mods.factorio.com`
  - API endpoint: `https://mods.factorio.com/api/mods`
  - Common endpoints:
    - GET `/api/mods/{mod_name}/full` - Get complete mod info including dependencies
    - GET `/download/{filename}` - Download mod file
- Error Handling:
  - Connection errors: "offline" error type
  - Timeouts (10-second default)
  - HTTP 404: "not_found" error type
  - HTTP 5xx: "server_error" error type
  - Custom `PortalAPIError` exception with error classification

## Data Storage

**Databases:**
- None - No traditional database used
- Local JSON config: `~/.factorio_mod_manager/config.json`
  - Configuration storage only, not application data

**File Storage:**
- Factorio mods folder (user-specified)
  - Default: `C:\Users\[Username]\AppData\Roaming\Factorio\mods` (Windows)
  - User configurable via UI
  - Stores `.zip` files of mods
  - Auto-detected on first run via `Config._detect_factorio_folder()`
- Backup folder: Optional version backups in mods folder
- Application data: `~/.factorio_mod_manager/`
  - `config.json` - User configuration
  - `logs/app.log` - Application log file

**Caching:**
- None - No persistent caching mechanism
- In-memory caching via `ModDownloader.get_installed_mods()` during session
- Mod metadata fetched fresh from portal each operation

## Authentication & Identity

**Auth Provider:**
- Factorio Portal Basic Auth
  - Implementation: HTTP Basic Auth via `requests.Session.auth`
  - Credentials: Username and API token pair
  - Optional: Can be left blank for public mods
  - Stored in: `~/.factorio_mod_manager/config.json`
  - Config keys: `username`, `token`

**No Centralized Auth:**
- No OAuth, SAML, or third-party identity providers
- Each user manages their own Factorio portal credentials
- Credentials never validated locally - only used for portal API calls

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service
- Local exception logging via Python logging module

**Logs:**
- File-based logging approach
  - Location: `~/.factorio_mod_manager/logs/app.log`
  - Created by: `factorio_mod_manager/utils/logger.py` - `setup_logger()`
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Timestamp: `%Y-%m-%d %H:%M:%S`
  - Levels: INFO (default), DEBUG, WARNING, ERROR
- Console output for debugging
- UI Log Viewer: `factorio_mod_manager/ui/logger_tab.py`
  - Displays logs in real-time via Queue integration
  - Receives logs from internal logger queue

## CI/CD & Deployment

**Hosting:**
- GitHub Releases (inferred from README.md release link)
- Distribution: Pre-built `.exe` files
- No cloud hosting or backend server

**Build Pipeline:**
- Local build with PyInstaller for `.exe`
- Local build with Inno Setup for Windows installer
- No CI/CD pipeline detected (manual builds)

**Deployment Method:**
- Standalone executable: Users download `.exe` and run
- Windows installer: Users run installer `.exe`
- No automatic updates (manual download from releases required)

## Environment Configuration

**Required env vars:**
- `.env` file support via python-dotenv
- No hardcoded required env vars in code
- All configuration via `config.json` or UI

**Config keys stored in `~/.factorio_mod_manager/config.json`:**
```json
{
  "mods_folder": "path/to/mods",     // User's Factorio mods directory
  "username": "factorio_username",   // Factorio portal username
  "token": "api_token_here",         // Factorio API token
  "theme": "dark",                   // UI theme
  "auto_backup": true,               // Backup mods before updating
  "download_optional": false,        // Include optional dependencies
  "auto_refresh": true,              // Auto-refresh mod list
  "max_workers": 4                   // Concurrent download threads
}
```

**Secrets location:**
- `~/.factorio_mod_manager/config.json` (user home directory)
- Credentials should be treated as secrets but stored in plain JSON
- No encryption mechanism implemented

## Webhooks & Callbacks

**Incoming:**
- None - Application is purely client-side, no server component

**Outgoing:**
- None - No webhooks or callbacks to external services
- One-way HTTP GET/POST requests to Factorio Mod Portal only

## Mod Portal Integration Details

**Dependency Resolution:**
- Recursive dependency fetching via `FactorioPortalAPI.get_mod_dependencies()`
- Parses `info_json.dependencies` from mod releases
- Dependency types:
  - Required: `dep_name >= version`
  - Optional: `(?) dep_name` or `? dep_name`
  - Incompatible: `! dep_name`
  - Expansions: Special handling for `space-age`, `elevated-rails` (paid DLC)

**Download Process:**
- URL construction: `{BASE_URL}/download/{filename}`
- Concurrent downloads: Up to 4 threads (configurable via `max_workers`)
- Streaming downloads with progress callbacks
- ZIP file validation after download
- Auto-extraction of mod files
- Implements: `factorio_mod_manager/core/downloader.py` - `ModDownloader` class

**Update Checking:**
- Portal version comparison against installed versions
- Status tracking: `ModStatus` enum (UP_TO_DATE, OUTDATED, UNKNOWN, ERROR)
- Implements: `factorio_mod_manager/core/checker.py` - `ModChecker` class

---

*Integration audit: 2026-04-09*
