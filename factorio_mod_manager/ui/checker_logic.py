"""Business logic for checker tab - thread operations separated from UI."""
from typing import Callable, Optional, List, Dict
from ..core import ModChecker, Mod
from ..core.update_guidance import UpdateGuidanceClassifier, GuidanceResult, UpdateClassification


class CheckerLogic:
    """Encapsulates all checker business logic and thread operations."""
    
    def __init__(self, checker: ModChecker, logger: Callable):
        """
        Initialize logic layer.
        
        Args:
            checker: ModChecker instance
            logger: Callable for progress logging (tab._log_progress)
        """
        self.checker = checker
        self.logger = logger
    
    def scan_mods(self) -> Dict[str, Mod]:
        """Scan mods folder and fetch portal data."""
        try:
            mods = self.checker.scan_mods()
            self.logger(f"[SCAN] ✓ Complete! Found {len(mods)} mod(s)", "success")
            return mods
        except Exception as e:
            self.logger(f"[SCAN] ✗ Error: {e}", "error")
            raise
    
    def check_updates(self, force_refresh: bool = False) -> tuple[Dict[str, Mod], bool]:
        """
        Check for updates (uses cached data if fresh).
        
        Returns:
            Tuple of (outdated_mods, was_refreshed)
        """
        try:
            outdated, was_refreshed = self.checker.check_updates(force_refresh)
            
            if was_refreshed:
                self.logger("[CHECK] ✓ Update check complete! (refreshed from portal)", "success")
            else:
                self.logger("[CHECK] ✓ Using cached data (no refresh needed)", "info")
            
            return outdated, was_refreshed
        except Exception as e:
            self.logger(f"[CHECK] ✗ Error: {e}", "error")
            raise
    
    def classify_updates(self, mods: dict) -> dict:
        """Classify all mods in the dict as Safe/Review/Risky.

        Only mods with status OUTDATED are meaningfully classified;
        others return SAFE (no update to assess).

        Returns:
            dict[str, GuidanceResult]
        """
        from ..core.mod import ModStatus
        results = {}
        for name, mod in mods.items():
            try:
                result = UpdateGuidanceClassifier.classify_mod(mod, mods)
                results[name] = result
                self.logger(f"[CLASSIFY] {name}: {result.classification.value}", "info")
            except Exception as exc:
                self.logger(f"[CLASSIFY] \u2717 {name}: {exc}", "error")
                results[name] = GuidanceResult(
                    classification=UpdateClassification.REVIEW,
                    rationale=["Classification failed \u2014 verify before applying"],
                    dep_delta_summary="unknown",
                )
        return results

    def update_mods(self, mod_names: List[str]) -> tuple[List[str], List[str]]:
        """
        Update multiple mods.
        
        Returns:
            Tuple of (successful_list, failed_list)
        """
        try:
            successful, failed = self.checker.update_mods(mod_names)
            
            self.logger(f"[UPDATE] ✓ Updated {len(successful)} mod(s)", "success")
            if failed:
                self.logger(f"[UPDATE] ✗ Failed: {', '.join(failed)}", "error")
            
            return successful, failed
        except Exception as e:
            self.logger(f"[UPDATE] ✗ Error: {e}", "error")
            raise
    
    def delete_mods(self, mod_names: List[str], mods_folder: str) -> tuple[List[str], List[str]]:
        """
        Delete multiple mods by removing their zip files.
        
        Returns:
            Tuple of (deleted_list, failed_list)
        """
        from pathlib import Path
        
        try:
            deleted = []
            failed = []
            
            for i, mod_name in enumerate(mod_names, 1):
                try:
                    mod = self.checker.mods.get(mod_name)
                    if not mod:
                        failed.append(f"{mod_name} (not found)")
                        continue
                    
                    mod_file = Path(mods_folder) / f"{mod.name}_{mod.version}.zip"
                    
                    if mod_file.exists():
                        mod_file.unlink()
                        deleted.append(mod_name)
                        self.logger(f"  [{i}/{len(mod_names)}] ✓ Deleted {mod_name}", "success")
                    else:
                        failed.append(f"{mod_name} (file not found)")
                        self.logger(f"  [{i}/{len(mod_names)}] ✗ File not found: {mod_name}", "error")
                
                except Exception as e:
                    failed.append(f"{mod_name} ({str(e)})")
                    self.logger(f"  [{i}/{len(mod_names)}] ✗ Error: {mod_name} - {e}", "error")
            
            # Remove from checker's mods dict
            for name in deleted:
                del self.checker.mods[name]
            
            self.logger(f"[DELETE] ✓ Complete! Deleted {len(deleted)} mod(s)", "success")
            if failed:
                self.logger(f"[DELETE] ✗ Failed: {len(failed)} mod(s)", "error")
            
            return deleted, failed
        
        except Exception as e:
            self.logger(f"[DELETE] ✗ Error: {e}", "error")
            raise
    
    def enable_mod(self, mod_name: str) -> None:
        """Enable *mod_name* by writing mod-list.json and updating in-memory state."""
        from ..core.mod_list import ModListStore

        store = ModListStore(self.checker.mods_folder)
        store.enable(mod_name)
        if mod_name in self.checker.mods:
            self.checker.mods[mod_name].enabled = True

    def disable_mod(self, mod_name: str) -> None:
        """Disable *mod_name* by writing mod-list.json without deleting its ZIP (D-15)."""
        from ..core.mod_list import ModListStore

        store = ModListStore(self.checker.mods_folder)
        store.disable(mod_name)
        if mod_name in self.checker.mods:
            self.checker.mods[mod_name].enabled = False

    def clean_backups(self, backup_folder: str) -> float:
        """
        Delete backup folder and return freed space in MB.
        
        Returns:
            Size freed in MB
        """
        from pathlib import Path
        import shutil
        
        try:
            backup_path = Path(backup_folder)
            
            if not backup_path.exists():
                self.logger("[CLEANUP] No backup folder found", "info")
                return 0.0
            
            # Calculate folder size before deletion
            folder_size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
            folder_size_mb = folder_size / (1024 * 1024)
            
            # Delete folder and contents
            shutil.rmtree(backup_path)
            
            self.logger(f"[CLEANUP] ✓ Complete! Deleted backup folder, freed {folder_size_mb:.2f} MB", "success")
            
            return folder_size_mb
        
        except Exception as e:
            self.logger(f"[CLEANUP] ✗ Error: {e}", "error")
            raise
