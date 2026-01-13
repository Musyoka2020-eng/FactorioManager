# Factorio Mod Manager

A comprehensive graphical tool for managing Factorio mods with automatic dependency resolution, mod searching, and batch operations.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)

## Features

✨ **Smart Mod Management**
- 🔍 Search mods from the Factorio mod portal with live preview
- 📥 Download mods with automatic dependency resolution
- ♻️ Check for and install mod updates
- 💾 Backup and restore mod versions
- 🗑️ Delete mods with confirmation

✨ **Dependency Handling**
- 🔗 Automatic recursive dependency resolution
- ❓ Optional dependency support (with user control)
- ⚠️ Conflict detection - warns about incompatible mods
- 📦 Shows all transitive dependencies before downloading

✨ **Advanced Features**
- 🔄 Multithreaded downloads (up to 4 concurrent mods)
- 📊 Real-time progress tracking with visual progress bars
- 📋 Download console with detailed logs
- 📥 Individual mod status in downloads sidebar
- 🌐 Cross-platform support (Windows, Linux, macOS)

## Quick Start

### Download & Install

1. **Download the latest release:** [FactorioModManager.exe](https://github.com/Musyoka2020-eng/FactorioManager/releases/latest)
   - No installation required - just run the executable!
   - Requires Windows 7+ with .NET Framework

2. **Run the application**
   - Double-click `FactorioModManager.exe`
   - Select your Factorio mods folder on first run

### Configure Your Factorio Mods Folder

On first launch:
1. Click **Browse** next to "📁 Mods Folder"
2. Navigate to your Factorio mods directory (typically `C:\Users\[YourUsername]\AppData\Roaming\Factorio\mods`)
3. Click **Select Folder**

### Basic Usage

#### Download a Mod
1. Go to the **Downloader** tab
2. Enter the mod name or URL (e.g., `jetpack` or `https://mods.factorio.com/mod/jetpack`)
3. Review dependencies shown in the info panel
4. Click **⬇️ Download**
5. Watch the progress in the downloads panel and sidebar
6. Optional dependencies are shown but not auto-downloaded (you choose whether to include them)

#### Check for Updates
1. Go to the **Checker** tab
2. Click **🔍 Scan Mods** to check for available updates
3. Mods with updates appear highlighted
4. Select mods and click **⬆️ Update** to install newer versions

#### Backup & Restore
1. Select one or more mods in the **Checker** tab
2. Click **💾 Backup** to create backup copies
3. Backups are stored in a `backup/` subfolder within your mods directory
4. Use **♻️ Restore** to restore from backups (if available)

#### Delete Mods
1. Select mods in the **Checker** tab
2. Click **🗑️ Delete** to remove them
3. Confirm the deletion

## Understanding Dependency Display

### Direct Dependencies (in search preview)
- **🔗 Required:** Mods that must be installed for this mod to work
- **❓ Optional:** Mods that add extra functionality if present
- **❌ Incompatible:** Mods that conflict with this one
- **💿 Requires DLC:** Paid expansions needed

### All Dependencies (will download)
- **📦** Shows all mods that will be downloaded, including:
  - The main mod you selected
  - All required dependencies
  - All dependencies of dependencies (recursive)
  - Optional dependencies (if you enabled them)

**Example:** Downloading `jetpack` shows:
- PickerTweaks (optional dependency of jetpack)
- stdlib (required by PickerTweaks)
- long-reach-fix (optional dependency of PickerTweaks)

## Conflict Detection

The app checks for conflicts in two ways:

1. **Between downloaded mods** - Warns if any mod you're downloading conflicts with another
2. **With installed mods** - Warns if what you're downloading conflicts with already-installed mods
3. **Incompatible dependencies** - Identifies mods that can't coexist

⚠️ **Note:** Incompatible mods will still download but won't work together in-game.

## Configuration

Settings are automatically saved in:
- **Windows:** `C:\Users\[YourUsername]\AppData\Local\FactorioModManager\config.ini`
- **Linux:** `~/.config/FactorioModManager/config.ini`
- **macOS:** `~/Library/Application Support/FactorioModManager/config.ini`

Settings include:
- Mods folder location
- Factorio API credentials (optional, for higher download limits)
- Download preferences
- Optional dependency settings

## Advanced: Factorio API Authentication

For higher download limits and faster downloads, you can add your Factorio credentials:

1. Get your API token from [mods.factorio.com](https://mods.factorio.com) → User Profile → Authentication
2. In the app, add your username and token to the settings
3. Credentials are stored locally and never shared

## Troubleshooting

### "Mods folder not found"
- Ensure the path to your mods folder is correct
- Check that the folder exists and you have read/write permissions

### Download fails with "404 Not Found"
- The mod may have been removed from the portal
- Try searching on [mods.factorio.com](https://mods.factorio.com) to confirm it exists
- Check the mod name spelling

### "Invalid ZIP file" error
- The download was corrupted
- Try downloading again
- If it persists, the mod may have a server-side issue

### Mod appears to be installed but game doesn't recognize it
- Factorio may require a restart to load new mods
- Check that the mod is enabled in-game (`Mods` → Enable)
- Verify the mod version is compatible with your Factorio version

### Status bar doesn't update during downloads
- This is normal - it updates as each mod completes
- Check the detailed progress in the Downloader tab console

## System Requirements

- **OS:** Windows 7+ (or Linux/macOS with Python 3.12+)
- **Disk Space:** 50MB for the app + space for mods
- **Internet:** Required for downloading mods and checking updates
- **.NET Framework:** Windows only (usually pre-installed)

## For Developers

### Building from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/FactorioManager.git
cd FactorioManager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python -m factorio_mod_manager.main
```

### Building the Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller FactorioModManager.spec --clean
```

The executable will be in `dist/FactorioModManager.exe`

## Architecture

- **Core:** `factorio_mod_manager/core/` - Download, update, and mod management logic
- **UI:** `factorio_mod_manager/ui/` - Tkinter GUI with multiple tabs
- **Utils:** `factorio_mod_manager/utils/` - Helpers, logging, configuration

### Key Components

- `portal.py` - Factorio mod portal API integration
- `downloader.py` - Mod downloading with dependency resolution
- `checker.py` - Update checking and mod management
- `main_window.py` - Main UI controller
- `downloader_tab.py` / `checker_tab.py` - Tab implementations

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Known Limitations

- Does not support Factorio mods with non-standard naming
- Cannot install mods from custom repositories (only factorio.com)
- Does not validate mod compatibility with specific Factorio versions in advance
- Multithreading limited to 4 concurrent downloads

## Roadmap

- [ ] Mod profile management (save/load mod configurations)
- [ ] Mod auto-update feature
- [ ] Integration with Factorio game launcher
- [ ] Web UI alternative to desktop app
- [ ] Linux AppImage and Snap packages

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Factorio mod portal API for mod data
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for web parsing
- [Tkinter](https://docs.python.org/3/library/tkinter.html) for the GUI
- Factorio community for feedback and suggestions

## Support

- **Bug Reports:** Open an issue on GitHub
- **Feature Requests:** Discuss in GitHub Discussions
- **Questions:** Check existing issues or open a Discussion

---

**Enjoy managing your Factorio mods!** 🎮

Made with ❤️ for the Factorio community
