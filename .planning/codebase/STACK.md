# Technology Stack

**Analysis Date:** 2026-04-09

## Languages

**Primary:**
- Python 3.12+ - All application code, UI, and core logic

## Runtime

**Environment:**
- Python 3.12+ (specified in `pyproject.toml`)

**Package Manager:**
- Poetry - Dependency management and packaging
- Lockfile: Implicit (Poetry uses poetry.lock)

## Frameworks

**GUI:**
- Tkinter - Built-in Python GUI framework (standard library)
  - Used for entire desktop UI in `factorio_mod_manager/ui/`
  - Custom dark theme with styled components
  - Multi-threaded UI updates via Queue integration

**HTTP/Web:**
- Requests 2.32.0 - HTTP client for API calls
  - Used in `factorio_mod_manager/core/portal.py` for Factorio Mod Portal API
  - Used in `factorio_mod_manager/core/downloader.py` for mod downloads
  - Session-based with optional HTTP Basic Auth

**HTML Parsing:**
- BeautifulSoup4 4.12.0 - HTML/XML parsing
  - Used in `factorio_mod_manager/core/portal.py` for parsing mod portal responses
  - Integrated with lxml for performance

**Image Processing:**
- Pillow 10.1.0 - Image manipulation
  - Used for icon handling and image processing in UI

**Configuration:**
- python-dotenv 1.0.0 - Environment variable management
  - Loads `.env` files for configuration

**XML Processing:**
- lxml 4.9.0 - Fast XML/HTML parsing library
  - Backend for BeautifulSoup4

## Testing

**Framework:**
- pytest 7.4.0 - Test runner and framework

## Code Quality

**Formatting:**
- black 23.12.0 - Code formatter

**Linting:**
- ruff 0.1.0 - Fast Python linter

## Build & Packaging

**Windows Executable:**
- PyInstaller - Compiles Python to executable
  - Config: `FactorioModManager.spec`
  - Output: Standalone `.exe` file in `build/` directory
  - See artifacts: `build/FactorioModManager/`

**Windows Installer:**
- Inno Setup - Windows installation wizard
  - Script: `FactorioModManager.iss`
  - Creates `.exe` installer for deployment

## Key Dependencies

**Critical:**
- requests 2.32.0 - Essential for Factorio Portal API communication
- beautifulsoup4 4.12.0 - Essential for parsing mod metadata
- tkinter - Essential for GUI (built-in library)

**Important:**
- pillow 10.1.0 - Image handling for UI
- lxml 4.9.0 - Performance optimization for parsing
- python-dotenv 1.0.0 - Configuration management

**Unused:**
- selenium 4.25.0 - Listed in `pyproject.toml` but not used in codebase (likely for future web scraping capability)

## Configuration

**Environment:**
- .env file support via python-dotenv
- JSON-based config file: `~/.factorio_mod_manager/config.json`
  - Manages mods folder path, credentials, UI theme, download settings
  - Auto-generates on first run with defaults

**Build:**
- `pyproject.toml` - Poetry configuration with all dependencies
- `FactorioModManager.spec` - PyInstaller specification for executable
- `FactorioModManager.iss` - Inno Setup installer configuration

## Platform Requirements

**Development:**
- Python 3.12 or later
- Windows 7+ for testing (DPI awareness code specific to Windows)
- Linux/macOS supported (cross-platform Tkinter support)

**Production:**
- Windows 7+ for distributed .exe
  - DPI awareness enabled for crisp rendering on high-resolution displays
- Python installation for source distribution
- Read/write access to Factorio mods folder

## Deployment

**Distribution Methods:**
1. Pre-compiled executable: `FactorioModManager.exe` (PyInstaller)
2. Windows installer: Via Inno Setup `.iss` script
3. Source distribution: Poetry package installation

**Logging:**
- File-based logs: `~/.factorio_mod_manager/logs/app.log`
- Console output during runtime
- UI log viewer tab with queue-based integration

---

*Stack analysis: 2026-04-09*
