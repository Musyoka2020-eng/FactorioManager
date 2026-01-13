"""Configuration management for Factorio Mod Manager."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Manage application configuration."""

    CONFIG_DIR = Path.home() / ".factorio_mod_manager"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    # Default configuration
    DEFAULTS = {
        "mods_folder": None,  # Will be auto-detected
        "username": None,
        "token": None,
        "theme": "dark",
        "auto_backup": True,
        "download_optional": False,
        "auto_refresh": True,
        "max_workers": 4,
    }

    def __init__(self):
        """Initialize configuration."""
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.data: Dict[str, Any] = self.DEFAULTS.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
        
        # Auto-detect Factorio mods folder if not set
        if not self.data.get("mods_folder"):
            self.data["mods_folder"] = self._detect_factorio_folder()

    def save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get configuration value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.data[key] = value
        self.save()

    def _detect_factorio_folder(self) -> Optional[str]:
        """Auto-detect Factorio mods folder based on OS."""
        import platform
        
        system = platform.system()
        home = Path.home()

        if system == "Windows":
            mods_path = home / "AppData" / "Roaming" / "Factorio" / "mods"
        elif system == "Linux":
            mods_path = home / ".factorio" / "mods"
        elif system == "Darwin":  # macOS
            mods_path = home / "Library" / "Application Support" / "factorio" / "mods"
        else:
            return None

        if mods_path.exists():
            return str(mods_path)
        return None


# Global config instance
config = Config()
