# Factorio Mod Manager

A graphical tool for managing Factorio mods. Handles downloading, dependency resolution, checking for updates, and basic mod operations.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)

## What it does

**Mod management**
- Search mods from the Factorio mod portal
- Download mods with automatic dependency resolution
- Check for and install mod updates
- Backup and restore mod versions
- Delete mods

**Dependency handling**
- Resolves dependencies recursively
- Handles optional dependencies (you choose whether to include them)
- Detects conflicts between mods
- Shows you what will be downloaded before you proceed

**Other features**
- Download multiple mods at once (up to 4 concurrent)
- Download logs and progress tracking
- Can save mod profiles to apply later

## Quick Start

### Download & Install

1. **Download the latest release:** [FactorioModManager.exe](https://github.com/Musyoka2020-eng/FactorioManager/releases/latest)

2. **Run the application**
   - Double-click on the installed app
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

1. Get the latest release: [FactorioModManager.exe](https://github.com/Musyoka2020-eng/FactorioManager/releases/latest)
2. Run it - no installation needed
3. On first run, select your Factorio mods folder (usually `C:\Users\[YourUsername]\AppData\Roaming\Factorio\mods`)

**Basic workflow**

- **Downloader tab:** Search for mods, review what will be downloaded, click Download
- **Checker tab:** Scan for updates, backup mods, delete mods
- **Profiles:** Save combinations of mods and apply them later

## Understanding Dependencies

When you search for a mod, you'll see:
- **Required:** Mods that need to be installed for this to work
- **Optional:** Extra mods that add features if you want them
- **Incompatible:** Mods that conflict with this one

When you download, it shows all the mods that will be installed - the one you want plus everything it needs (and what those need, etc.). Optional dependencies are included if you enable that option.

## Conflict Detection

The app checks if mods you're downloading conflict with each other or with mods you already have. It will warn you, but it doesn't stop the download - that's on you.

## Configuration

Settings are saved locally:
- Windows: `C:\Users\[YourUsername]\AppData\Local\FactorioModManager\config.ini`
- Linux: `~/.config/FactorioModManager/config.ini`
- macOS: `~/Library/Application Support/FactorioModManager/config.ini`

You can optionally add your Factorio API credentials for higher download limits (get your token from [mods.factorio.com](https://mods.factorio.com) user profile).

## Limitations & Known Issues

- **UI is basic:** I'm not great at UI design yet, so the interface isn't polished. It works, but it's clunky
- **Text field issues:** Search fields sometimes feel slow or unresponsive
- **Profile features:** Profile management works but could use better UX
- **Error messages:** Some are technical/unclear - improving these as I learn
- **Only on Windows:** The .exe build works on Windows. Linux/macOS requires running from source
- **No mod conflicts:** The app detects conflicts but doesn't prevent installation - if you install incompatible mods, they just won't load

## Troubleshooting

**"Mods folder not found"**
- Make sure the path is correct and you have read/write permissions

**Download fails with "404 Not Found"**
- The mod may have been removed or the name is wrong
- Try searching on [mods.factorio.com](https://mods.factorio.com)

**"Invalid ZIP file" error**
- Download got corrupted - try again or the mod might have a server issue

**Mod installed but game doesn't recognize it**
- Factorio needs to be restarted to load new mods
- Check that the mod is enabled in-game (Mods → Enable)
- Make sure the mod version matches your Factorio version

## System Requirements

- Windows 7+ (or Python 3.12+ for Linux/macOS)
- Disk space for mods
- Internet for downloading

## For Developers

**Running from source**

```bash
git clone https://github.com/Musyoka2020-eng/FactorioManager.git
cd FactorioManager
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m factorio_mod_manager.main
```

**Building the .exe**

```bash
pip install pyinstaller
pyinstaller FactorioModManager.spec --clean
```

Output is in `dist/FactorioModManager.exe`

## Architecture

- `factorio_mod_manager/core/` - Download, update, dependency logic
- `factorio_mod_manager/ui/` - GUI (tkinter)
- `factorio_mod_manager/utils/` - Helpers, logging, config

Key files:
- `portal.py` - API integration
- `downloader.py` - Download and dependency resolution
- `checker.py` - Update checking
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
