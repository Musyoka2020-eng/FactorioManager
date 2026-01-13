"""Mod checker and updater."""
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .mod import Mod, ModStatus
from .portal import FactorioPortalAPI
from .downloader import ModDownloader
from ..utils import parse_mod_info


class ModChecker:
    """Check for mod updates and manage versions."""

    def __init__(
        self,
        mods_folder: str,
        username: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """
        Initialize mod checker.
        
        Args:
            mods_folder: Path to Factorio mods folder
            username: Factorio username
            token: Factorio API token
        """
        self.mods_folder = Path(mods_folder)
        self.portal = FactorioPortalAPI(username, token)
        self.downloader = ModDownloader(str(self.mods_folder), username, token)
        self.mods: Dict[str, Mod] = {}
        self.last_update_check: Optional[datetime] = None
        
        # Callback for progress updates
        self.progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback
        self.downloader.set_progress_callback(callback)

    def _log_progress(self, message: str) -> None:
        """Log progress message."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    def scan_mods(self) -> Dict[str, Mod]:
        """
        Scan the mods folder for installed mods.
        
        Returns:
            Dictionary mapping mod names to Mod objects
        """
        self._log_progress("Scanning mods folder...")
        self.mods = {}
        
        if not self.mods_folder.exists():
            self._log_progress(f"Mods folder not found: {self.mods_folder}")
            return self.mods
        
        mod_files = list(self.mods_folder.glob("*.zip"))
        self._log_progress(f"Found {len(mod_files)} mod files")
        
        # First pass: parse local mod info
        local_mods = {}
        for mod_file in mod_files:
            try:
                # Parse filename: modname_version.zip
                filename = mod_file.stem
                if '_' in filename:
                    name, version = filename.rsplit('_', 1)
                else:
                    name = filename
                    version = "0.0.0"
                
                # Try to parse info.json for more details
                info = parse_mod_info(mod_file)
                
                mod = Mod(
                    name=name,
                    title=info.get("title", name) if info else name,
                    version=version,
                    author=info.get("author", "Unknown") if info else "Unknown",
                    description=info.get("description", "") if info else "",
                    file_path=str(mod_file),
                    release_date=datetime.fromtimestamp(mod_file.stat().st_mtime),
                    file_size=mod_file.stat().st_size,
                    raw_data=info or {},
                )
                
                local_mods[name] = mod
            
            except Exception as e:
                self._log_progress(f"  ✗ Error parsing {mod_file.name}: {e}")
        
        # Second pass: fetch portal data in parallel
        self._log_progress(f"Fetching portal data for {len(local_mods)} mods (parallel)...")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all portal fetch tasks
            future_to_name = {
                executor.submit(self.portal.get_mod, name): name 
                for name in local_mods.keys()
            }
            
            # Process results as they complete
            for future in as_completed(future_to_name):
                mod_name = future_to_name[future]
                mod = local_mods[mod_name]
                
                try:
                    mod_data = future.result()
                    if mod_data:
                        mod.downloads = mod_data.get("downloads_count", 0)
                        mod.homepage = mod_data.get("homepage", "")
                        
                        # Get latest version
                        releases = mod_data.get("releases", [])
                        if releases:
                            latest = releases[-1]
                            mod.latest_version = latest.get("version", mod.version)
                            mod.update_status()
                        else:
                            mod.status = ModStatus.UNKNOWN
                    else:
                        mod.status = ModStatus.UNKNOWN
                    
                    self.mods[mod_name] = mod
                    self._log_progress(f"  ✓ {mod} (Downloads: {mod.downloads:,})")
                
                except Exception as e:
                    self._log_progress(f"  ✗ Error fetching {mod_name}: {e}")
                    mod.status = ModStatus.UNKNOWN
                    self.mods[mod_name] = mod
        
        # Record when we last checked
        self.last_update_check = datetime.now()
        
        return self.mods

    def check_updates(self, force_refresh: bool = False) -> tuple[Dict[str, Mod], bool]:
        """
        Check for updates for all installed mods.
        
        Uses cached data if last check was < 10 minutes ago (unless force_refresh=True).
        
        Args:
            force_refresh: Force refresh from portal even if data is fresh
        
        Returns:
            Tuple of (outdated_mods_dict, was_refreshed_bool)
        """
        outdated = {}
        was_refreshed = False
        
        if not self.mods:
            self._log_progress("No mods installed")
            return outdated, was_refreshed
        
        # Check if data is fresh (< 10 minutes old)
        now = datetime.now()
        data_is_fresh = (
            self.last_update_check is not None
            and (now - self.last_update_check).total_seconds() < 600  # 10 minutes
        )
        
        if data_is_fresh and not force_refresh:
            # Use cached data
            self._log_progress("\nUpdate check (using cached data)...")
            for mod in self.mods.values():
                if mod.is_outdated:
                    outdated[mod.name] = mod
            
            # Show when data was last checked
            if self.last_update_check is not None:
                time_diff = (now - self.last_update_check).total_seconds()
                mins = int(time_diff // 60)
                secs = int(time_diff % 60)
                time_str = f"{mins}m {secs}s ago" if mins > 0 else f"{secs}s ago"
                self._log_progress(f"✓ Data is fresh ({time_str})")
            self._log_progress(f"Updates available: {len(outdated)}")
            
            return outdated, was_refreshed
        
        # Refresh from portal
        self._log_progress("\nChecking for updates (refreshing from portal)...")
        was_refreshed = True
        
        # Fetch portal data in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all portal fetch tasks
            future_to_name = {
                executor.submit(self.portal.get_mod, mod_name): mod_name 
                for mod_name in self.mods.keys()
            }
            
            # Process results as they complete
            for future in as_completed(future_to_name):
                mod_name = future_to_name[future]
                mod = self.mods[mod_name]
                
                try:
                    self._log_progress(f"Checking {mod_name}...")
                    
                    mod_data = future.result()
                    if not mod_data:
                        mod.status = ModStatus.UNKNOWN
                        self._log_progress(f"  ? {mod_name} not found on portal")
                        continue
                    
                    releases = mod_data.get("releases", [])
                    if releases:
                        latest_release = releases[-1]
                        latest_version = latest_release.get("version", mod.version)
                        mod.latest_version = latest_version
                        mod.update_status()
                        
                        if mod.is_outdated:
                            outdated[mod_name] = mod
                            self._log_progress(
                                f"  ⬆ Update available: {mod.version} → {latest_version}"
                            )
                        else:
                            self._log_progress(f"  ✓ Up to date ({mod.version})")
                    else:
                        mod.status = ModStatus.UNKNOWN
                        self._log_progress(f"  ? No releases found for {mod_name}")
                
                except Exception as e:
                    mod.status = ModStatus.ERROR
                    self._log_progress(f"  ✗ Error checking {mod_name}: {e}")
        
        # Update timestamp and report
        self.last_update_check = datetime.now()
        self._log_progress(f"\nUpdates available: {len(outdated)}")
        
        return outdated, was_refreshed

    def update_mod(self, mod_name: str, current: int = 1, total: int = 1) -> bool:
        """
        Update a single mod.
        
        Args:
            mod_name: Name of the mod to update
            current: Current mod number (for progress display)
            total: Total mods to update (for progress display)
            
        Returns:
            True if successful, False otherwise
        """
        if mod_name not in self.mods:
            self._log_progress(f"  [{current}/{total}] ✗ {mod_name} - not installed")
            return False
        
        mod = self.mods[mod_name]
        
        # Check if mod is already up to date
        if mod.version == mod.latest_version:
            self._log_progress(f"  [{current}/{total}] ℹ {mod.name} {mod.version} - already up to date")
            return False
        
        # Download new version
        if not mod.latest_version:
            self._log_progress(f"  [{current}/{total}] ℹ {mod.name} - no update available")
            return False
        
        # Backup current version
        if mod.file_path:
            try:
                # Create backup folder inside mod folder
                mod_folder = Path(mod.file_path).parent
                backup_folder = mod_folder / "backup"
                backup_folder.mkdir(exist_ok=True)
                
                # Copy to backup folder with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{Path(mod.file_path).stem}_{timestamp}.zip"
                backup_path = backup_folder / backup_filename
                
                shutil.copy2(mod.file_path, backup_path)
                self._log_progress(f"  [{current}/{total}] ↻ Backed up {mod.name} {mod.version} to backup/")
            except Exception as e:
                self._log_progress(f"  [{current}/{total}] ⚠ Warning backing up {mod.name}: {e}")
        
        self._log_progress(f"  [{current}/{total}] ⬇ Downloading {mod.name} {mod.version} → {mod.latest_version}...")
        
        mod.version = mod.latest_version
        success = self.downloader.download_mod(mod, force=True)
        
        if success:
            # Remove old version
            if mod.file_path and Path(mod.file_path).exists():
                try:
                    Path(mod.file_path).unlink()
                    self._log_progress(f"  [{current}/{total}] ✓ Updated {mod.name} to {mod.latest_version}")
                except Exception as e:
                    self._log_progress(f"  [{current}/{total}] ⚠ Warning removing old {mod.name}: {e}")
            
            mod.file_path = str(self.mods_folder / f"{mod_name}_{mod.latest_version}.zip")
            mod.status = ModStatus.UP_TO_DATE
        else:
            self._log_progress(f"  [{current}/{total}] ✗ Failed to download {mod.name}")
        
        return success

    def update_mods(self, mod_names: Optional[List[str]] = None) -> tuple[List[str], List[str]]:
        """
        Update multiple mods.
        
        Args:
            mod_names: List of mod names to update. If None, update all outdated.
            
        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        if mod_names is None:
            # Update all outdated
            mod_names = [
                name for name, mod in self.mods.items() if mod.is_outdated
            ]
        
        self._log_progress(f"\n═══════════════════════════════════════════════════════")
        self._log_progress(f"Updating {len(mod_names)} mod(s)...")
        self._log_progress(f"═══════════════════════════════════════════════════════")
        successful = []
        failed = []
        
        for i, mod_name in enumerate(mod_names, 1):
            try:
                if self.update_mod(mod_name, current=i, total=len(mod_names)):
                    successful.append(mod_name)
                else:
                    failed.append(mod_name)
            except Exception as e:
                self._log_progress(f"  [{i}/{len(mod_names)}] ✗ Error updating {mod_name}: {e}")
                failed.append(mod_name)
        
        self._log_progress(f"═══════════════════════════════════════════════════════")
        self._log_progress(f"✓ {len(successful)} successful, ✗ {len(failed)} failed")
        self._log_progress(f"═══════════════════════════════════════════════════════")
        
        return successful, failed

    def uninstall_mod(self, mod_name: str) -> bool:
        """
        Uninstall a mod by deleting its zip file.
        
        Args:
            mod_name: Name of the mod to uninstall
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if mod_name not in self.mods:
                self._log_progress(f"✗ {mod_name} not found in installed mods")
                return False
            
            mod = self.mods[mod_name]
            if not mod.file_path:
                self._log_progress(f"✗ {mod_name} has no file path")
                return False
            
            mod_file = Path(mod.file_path)
            
            if not mod_file.exists():
                self._log_progress(f"✗ Mod file not found: {mod_file}")
                return False
            
            # Delete the mod file
            mod_file.unlink()
            self._log_progress(f"✓ Uninstalled {mod_name}@{mod.version}")
            
            # Remove from mods dictionary
            del self.mods[mod_name]
            return True
        
        except Exception as e:
            self._log_progress(f"✗ Error uninstalling {mod_name}: {e}")
            return False

    def backup_mod(self, mod_name: str, backup_folder: str) -> bool:
        """
        Backup a mod to a specified folder.
        
        Args:
            mod_name: Name of the mod to backup
            backup_folder: Path to backup folder
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if mod_name not in self.mods:
                self._log_progress(f"✗ {mod_name} not found in installed mods")
                return False
            
            mod = self.mods[mod_name]
            if not mod.file_path:
                self._log_progress(f"✗ {mod_name} has no file path")
                return False
            
            mod_file = Path(mod.file_path)
            backup_path = Path(backup_folder)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Verify source file exists
            if not mod_file.exists():
                self._log_progress(f"✗ Source mod file not found: {mod_file}")
                return False
            
            # Copy mod to backup folder (not move - we want to keep the original)
            backup_file = backup_path / mod_file.name
            shutil.copy2(str(mod_file), str(backup_file))
            
            # Verify backup was created
            if not backup_file.exists():
                self._log_progress(f"✗ Backup file was not created: {backup_file}")
                return False
            
            # Verify original file still exists
            if not mod_file.exists():
                self._log_progress(f"✗ Original mod file was removed during backup: {mod_file}")
                return False
            
            self._log_progress(f"✓ Backed up {mod_name} to {backup_file}")
            return True
        
        except Exception as e:
            self._log_progress(f"✗ Error backing up {mod_name}: {e}")
            return False

    def restore_mod(self, backup_file: str, mods_folder: Optional[str] = None) -> bool:
        """
        Restore a mod from backup.
        
        Args:
            backup_file: Path to backup mod file
            mods_folder: Optional mods folder to restore to (defaults to configured folder)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                self._log_progress(f"✗ Backup file not found: {backup_file}")
                return False
            
            restore_to = Path(mods_folder or self.mods_folder)
            restore_to.mkdir(parents=True, exist_ok=True)
            
            # Copy backup to mods folder
            restore_file = restore_to / backup_path.name
            shutil.copy2(backup_path, restore_file)
            self._log_progress(f"✓ Restored {backup_path.name} from backup")
            return True
        
        except Exception as e:
            self._log_progress(f"✗ Error restoring mod: {e}")
            return False
    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about installed mods.
        
        Returns:
            Dictionary with counts
        """
        return {
            "total": len(self.mods),
            "up_to_date": sum(1 for m in self.mods.values() if m.status == ModStatus.UP_TO_DATE),
            "outdated": sum(1 for m in self.mods.values() if m.status == ModStatus.OUTDATED),
            "unknown": sum(1 for m in self.mods.values() if m.status == ModStatus.UNKNOWN),
            "errors": sum(1 for m in self.mods.values() if m.status == ModStatus.ERROR),
        }
